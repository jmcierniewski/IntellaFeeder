"""Contrôles amont avant génération.

Enjeu : Intella ne permet PAS de revérifier les réglages d'une source après
import — ce qui passe ici part en production tel quel.
"""

import config
import models
import validation


def _params(**over):
    base = {"user": "jdoe", "case": "D:\\Cas\\X", "output": "D:\\out",
            "exe": "D:\\Intella\\IntellaCmd.exe"}
    base.update(over)
    return base


def _source(path="D:\\Cas\\Source", stype=config.SOURCE_TYPE_FOLDER):
    return models.Source(name="s", path=path, source_type=stype)


class TestErreursBloquantes:
    def test_utilisateur_obligatoire(self):
        errors, _ = validation.collect([_source()], _params(user="  "), True)
        assert len(errors) == 1

    def test_emplacement_de_cas_obligatoire(self):
        errors, _ = validation.collect([_source()], _params(case=""), True)
        assert len(errors) == 1

    def test_sortie_obligatoire(self):
        errors, _ = validation.collect([_source()], _params(output=""), True)
        assert len(errors) == 1

    def test_exe_obligatoire(self):
        errors, _ = validation.collect([_source()], _params(exe=""), True)
        assert len(errors) == 1

    def test_aucune_source(self):
        errors, _ = validation.collect([], _params(), True)
        assert len(errors) == 1

    def test_taches_cochees_mais_fichier_illisible(self):
        s = _source()
        s.selected_task_ids = {"uuid-1"}
        errors, _ = validation.collect([s], _params(), False)
        assert len(errors) == 1

    def test_taches_non_cochees_fichier_illisible_ok(self):
        errors, _ = validation.collect([_source()], _params(), False)
        assert errors == []

    def test_cumul_des_erreurs(self):
        errors, _ = validation.collect([], _params(user="", case="", output="", exe=""), True)
        assert len(errors) == 5


class TestAvertissements:
    def test_chemin_relatif(self):
        """IntellaCmd exige des chemins absolus."""
        _e, warnings = validation.collect([_source(path="Cas\\relatif")], _params(), True)
        assert any("absolu" in w.lower() for w in warnings)

    def test_chemin_introuvable(self, tmp_path):
        _e, warnings = validation.collect(
            [_source(path=str(tmp_path / "absent"))], _params(), True)
        assert len(warnings) >= 1

    def test_chemin_existant_sans_avertissement(self, tmp_path):
        exe = tmp_path / "IntellaCmd.exe"          # exe réel : sinon warning « introuvable »
        exe.write_bytes(b"")
        _e, warnings = validation.collect(
            [_source(path=str(tmp_path))], _params(exe=str(exe)), True)
        assert warnings == []

    def test_segment_non_initial(self, tmp_path):
        img = tmp_path / "img.E02"
        img.write_bytes(b"")
        _e, warnings = validation.collect(
            [_source(path=str(img), stype=config.SOURCE_TYPE_DISK_IMAGE)], _params(), True)
        assert any("segment" in w.lower() for w in warnings)

    def test_exe_introuvable_est_un_avertissement(self, tmp_path):
        """Ne bloque pas : l'exe peut être sur un partage monté plus tard."""
        errors, warnings = validation.collect(
            [_source(path=str(tmp_path))], _params(exe=str(tmp_path / "IntellaCmd.exe")), True)
        assert errors == [] and len(warnings) == 1
