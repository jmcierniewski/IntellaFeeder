"""Analyse des logs d'import (bouton « Valider les opérations »).

Point sensible : les lignes de bootstrap logback (« Could NOT find resource »)
apparaissent dans TOUS les logs IntellaCmd et ne sont pas des erreurs — les
prendre pour telles ferait passer chaque import réussi pour un échec.
"""

import os

import op_validation


def _log(tmp_path, name, content):
    p = tmp_path / name
    p.write_text(content, encoding="utf-8")
    return str(p)


class TestParseImportLog:
    def test_ajout_reussi(self, tmp_path):
        p = _log(tmp_path, "ok.log", "blabla\nAdded new source: D:\\Cas\\Source1 [urn:uuid:1234]\nfin\n")
        info = op_validation.parse_import_log(p)
        assert info["ok"] is True
        assert info["evidence"] == "D:\\Cas\\Source1"
        assert info["message"] == ""

    def test_ajout_sans_uuid(self, tmp_path):
        p = _log(tmp_path, "ok2.log", "Added new source: D:\\Cas\\S2\n")
        assert op_validation.parse_import_log(p)["evidence"] == "D:\\Cas\\S2"

    def test_bootstrap_logback_ignore(self, tmp_path):
        """« Could NOT find resource » de logback ≠ échec d'import."""
        p = _log(tmp_path, "boot.log",
                 "14:34:44,187 |-INFO in ch.qos.logback.classic - Could NOT find resource "
                 "[logback-test.scmo]\nAdded new source: D:\\Cas\\S3\n")
        info = op_validation.parse_import_log(p)
        assert info["ok"] is True and info["message"] == ""

    def test_echec_validation(self, tmp_path):
        p = _log(tmp_path, "ko.log", "Validation failed: image corrompue\n")
        info = op_validation.parse_import_log(p)
        assert info["ok"] is False and "Validation failed" in info["message"]

    def test_ajout_puis_erreur_signale_les_deux(self, tmp_path):
        p = _log(tmp_path, "mixte.log", "Added new source: D:\\Cas\\S4\nException: boom\n")
        info = op_validation.parse_import_log(p)
        assert info["ok"] is True and "boom" in info["message"]

    def test_aucune_confirmation(self, tmp_path):
        p = _log(tmp_path, "vide.log", "rien d'utile\n")
        info = op_validation.parse_import_log(p)
        assert info["ok"] is False and info["message"]

    def test_log_illisible(self, tmp_path):
        info = op_validation.parse_import_log(str(tmp_path / "absent.log"))
        assert info["ok"] is False and info["evidence"] is None


class TestRuns:
    def test_list_runs_trie_et_filtre(self, tmp_path):
        for d in ("20260101_0900", "20260315_1830", "pas_un_run", "20251231_2359"):
            (tmp_path / d).mkdir()
        (tmp_path / "20260101_0900" / "x.log").write_text("", encoding="utf-8")
        assert op_validation.list_runs(str(tmp_path)) == [
            "20251231_2359", "20260101_0900", "20260315_1830"]

    def test_latest_run_dir(self, tmp_path):
        (tmp_path / "20260101_0900").mkdir()
        (tmp_path / "20260315_1830").mkdir()
        assert op_validation.latest_run_dir(str(tmp_path)).endswith("20260315_1830")

    def test_latest_run_dir_ancien_format_plat(self, tmp_path):
        """Sans sous-dossier horodaté, on analyse le dossier logs lui-même."""
        assert op_validation.latest_run_dir(str(tmp_path)) == str(tmp_path)

    def test_list_runs_dossier_absent(self, tmp_path):
        assert op_validation.list_runs(str(tmp_path / "absent")) == []


class TestScanLogs:
    def test_ne_lit_que_les_log(self, tmp_path):
        _log(tmp_path, "a.log", "Added new source: D:\\A\n")
        _log(tmp_path, "b.LOG", "Added new source: D:\\B\n")
        _log(tmp_path, "c.txt", "Added new source: D:\\C\n")
        noms = [r["file"] for r in op_validation.scan_logs(str(tmp_path))]
        assert noms == ["a.log", "b.LOG"]

    def test_dossier_absent(self, tmp_path):
        assert op_validation.scan_logs(str(tmp_path / "absent")) == []
