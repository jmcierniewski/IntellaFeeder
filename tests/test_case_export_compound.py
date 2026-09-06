"""Inventaire d'un cas compound : un ``-exportSourceList`` par sous-cas.

``run_export_subcases`` orchestre N appels et fusionne. IntellaCmd n'est jamais
lancé ici : ``run_export_source_list`` est remplacé par un faux, ce qui laisse
tester ce qui compte vraiment — la fusion, l'attribution des sources à leur
sous-cas, et surtout la **tolérance aux échecs partiels**.

Contrat verrouillé : un sous-cas en échec n'interrompt pas les autres, mais
l'appelant doit pouvoir dire que l'inventaire est partiel (``subcase_reports``).
Une exception n'est levée que si AUCUN sous-cas n'a pu être lu.
"""

import pytest

import case_export


def sub(name, path, exists=True, error=""):
    return {"name": name, "path": path, "exists": exists, "error": error,
            "user": "", "size": 0, "authorized_users": []}


def fake_export(rows_by_case, taches=None, fail=()):
    """Faux ``run_export_source_list`` : réponses figées par chemin de cas."""
    def _run(exe, user, case_loc, log, extra_args="", timeout_min=30):
        if case_loc in fail:
            raise RuntimeError("IntellaCmd a renvoyé le code 1")
        noms = rows_by_case[case_loc]
        rows = [{"Nom": n, "Type": "Dossier/Fichier", "Chemin": f"{case_loc}\\{n}"}
                for n in noms]
        inv = {
            "existing_paths": {f"{case_loc}\\{n}".lower() for n in noms},
            "known_bytes": 100 * len(noms),
            "folder_unknown": [],
            "case_tasks": list((taches or {}).get(case_loc, [])),
            "sources_detail": [{"name": n} for n in noms],
            "xml_path": f"{case_loc}\\sources.xml",
        }
        return rows, list(case_export.DISPLAY_COLUMNS), inv
    return _run


@pytest.fixture
def journal():
    lignes = []
    return lignes, lignes.append


class TestFusion:
    def test_sources_attribuees_a_leur_sous_cas(self, monkeypatch, journal):
        _lines, log = journal
        monkeypatch.setattr(case_export, "run_export_source_list",
                            fake_export({"A": ["s1", "s2"], "B": ["s3"]}))
        rows, columns, inv = case_export.run_export_subcases(
            "x.exe", "u", [sub("Sub A", "A"), sub("Sub B", "B")], log,
            case_name="Compound", case_path="C")

        assert columns[0] == case_export.SUBCASE_COLUMN
        assert [r[case_export.SUBCASE_COLUMN] for r in rows] == ["Sub A", "Sub A", "Sub B"]
        assert inv["source_count"] == 3
        assert inv["known_bytes"] == 300
        assert inv["is_compound"] is True
        assert inv["case_name"] == "Compound"

    def test_detail_porte_le_sous_cas(self, monkeypatch, journal):
        _lines, log = journal
        monkeypatch.setattr(case_export, "run_export_source_list",
                            fake_export({"A": ["s1"], "B": ["s2"]}))
        _rows, _cols, inv = case_export.run_export_subcases(
            "x.exe", "u", [sub("Sub A", "A"), sub("Sub B", "B")], log)
        assert [d["subcase"] for d in inv["sources_detail"]] == ["Sub A", "Sub B"]
        assert [d["subcase_path"] for d in inv["sources_detail"]] == ["A", "B"]

    def test_un_xml_par_sous_cas_lu(self, monkeypatch, journal):
        _lines, log = journal
        monkeypatch.setattr(case_export, "run_export_source_list",
                            fake_export({"A": ["s1"], "B": ["s2"]}))
        _rows, _cols, inv = case_export.run_export_subcases(
            "x.exe", "u", [sub("Sub A", "A"), sub("Sub B", "B")], log)
        assert inv["xml_paths"] == ["A\\sources.xml", "B\\sources.xml"]
        assert inv["xml_path"] == "A\\sources.xml"

    def test_taches_dedupliquees_entre_sous_cas(self, monkeypatch, journal):
        _lines, log = journal
        meme_tache = {"id": "uuid-different", "name": "OCR", "condition": "ALL"}
        autre = dict(meme_tache, id="autre-uuid")
        monkeypatch.setattr(case_export, "run_export_source_list", fake_export(
            {"A": ["s1"], "B": ["s2"]}, taches={"A": [meme_tache], "B": [autre]}))
        _rows, _cols, inv = case_export.run_export_subcases(
            "x.exe", "u", [sub("Sub A", "A"), sub("Sub B", "B")], log)
        # Même signature (l'UUID est hors signature) : une seule tâche retenue.
        assert len(inv["case_tasks"]) == 1


class TestEchecsPartiels:
    def test_sous_cas_inaccessible_reporte_sans_appel(self, monkeypatch, journal):
        _lines, log = journal
        monkeypatch.setattr(case_export, "run_export_source_list",
                            fake_export({"A": ["s1"]}))
        rows, _cols, inv = case_export.run_export_subcases(
            "x.exe", "u",
            [sub("Sub A", "A"), sub("Absent", "Z", exists=False, error="hors du poste")],
            log)
        assert len(rows) == 1
        ko = [r for r in inv["subcase_reports"] if not r["ok"]]
        assert len(ko) == 1 and ko[0]["error"] == "hors du poste"

    def test_echec_intellacmd_nempeche_pas_les_autres(self, monkeypatch, journal):
        _lines, log = journal
        monkeypatch.setattr(case_export, "run_export_source_list",
                            fake_export({"A": ["s1"], "B": []}, fail={"B"}))
        rows, _cols, inv = case_export.run_export_subcases(
            "x.exe", "u", [sub("Sub A", "A"), sub("Sub B", "B")], log)
        assert len(rows) == 1
        assert [r["ok"] for r in inv["subcase_reports"]] == [True, False]
        assert "code 1" in inv["subcase_reports"][1]["error"]

    def test_rapport_par_sous_cas_lu(self, monkeypatch, journal):
        _lines, log = journal
        monkeypatch.setattr(case_export, "run_export_source_list",
                            fake_export({"A": ["s1", "s2"]}))
        _rows, _cols, inv = case_export.run_export_subcases(
            "x.exe", "u", [sub("Sub A", "A")], log)
        (rep,) = inv["subcase_reports"]
        assert rep["ok"] and rep["source_count"] == 2 and rep["bytes"] == 200

    def test_tous_en_echec_leve(self, monkeypatch, journal):
        _lines, log = journal
        monkeypatch.setattr(case_export, "run_export_source_list",
                            fake_export({"A": []}, fail={"A"}))
        with pytest.raises(RuntimeError):
            case_export.run_export_subcases("x.exe", "u", [sub("Sub A", "A")], log)

    def test_compound_sans_sous_cas_ne_leve_pas(self, journal):
        _lines, log = journal
        rows, _cols, inv = case_export.run_export_subcases("x.exe", "u", [], log)
        assert rows == [] and inv["source_count"] == 0
