"""JSON d'import par source (import résilient : 1 fichier par source).

Contrats : champs obligatoires d'IntellaCmd présents, options de profil
fusionnées **sans écraser** les champs de base, encodage ASCII échappé.
"""

import json
import os

import config
import json_builder
import models


def _source(name="Scellé 1", path="D:\\Cas\\Source", stype=config.SOURCE_TYPE_FOLDER):
    return models.Source(name=name, path=path, source_type=stype)


def _lire(path):
    with open(path, encoding="utf-8") as f:
        return json.load(f)


class TestBuildSingleSourceJson:
    def test_champs_obligatoires(self, tmp_path):
        p = json_builder.build_single_source_json(
            _source(), "UTC", None, str(tmp_path), "s.json")
        obj = _lire(p)["sources"][0]
        assert obj["name"] == "Scellé 1"
        assert obj["evidencePath"] == "D:\\Cas\\Source"
        assert obj["sourceType"] == config.SOURCE_TYPE_FOLDER
        assert obj["timezone"] == "UTC"

    def test_une_seule_source_par_fichier(self, tmp_path):
        p = json_builder.build_single_source_json(
            _source(), "UTC", None, str(tmp_path), "s.json")
        assert len(_lire(p)["sources"]) == 1

    def test_taskfile_absent_si_aucune_tache(self, tmp_path):
        p = json_builder.build_single_source_json(
            _source(), "UTC", None, str(tmp_path), "s.json")
        assert "taskFile" not in _lire(p)["sources"][0]

    def test_taskfile_present(self, tmp_path):
        p = json_builder.build_single_source_json(
            _source(), "UTC", "D:\\t\\task_T1.json", str(tmp_path), "s.json")
        assert _lire(p)["sources"][0]["taskFile"] == "D:\\t\\task_T1.json"

    def test_options_de_profil_fusionnees(self, tmp_path):
        p = json_builder.build_single_source_json(
            _source(), "UTC", None, str(tmp_path), "s.json",
            options={"indexArchives": False, "sourceTypeFilter": "application/pdf"})
        obj = _lire(p)["sources"][0]
        assert obj["indexArchives"] is False
        assert obj["sourceTypeFilter"] == "application/pdf"

    def test_options_ne_peuvent_pas_ecraser_les_champs_de_base(self, tmp_path):
        """Un profil mal formé ne doit pas pouvoir détourner le chemin d'évidence."""
        p = json_builder.build_single_source_json(
            _source(), "UTC", None, str(tmp_path), "s.json",
            options={"evidencePath": "D:\\PIRATE", "name": "usurpé", "timezone": "CET"})
        obj = _lire(p)["sources"][0]
        assert obj["evidencePath"] == "D:\\Cas\\Source"
        assert obj["name"] == "Scellé 1"
        assert obj["timezone"] == "UTC"

    def test_ascii_echappe(self, tmp_path):
        p = json_builder.build_single_source_json(
            _source(name="Scellé é"), "UTC", None, str(tmp_path), "s.json")
        with open(p, encoding="utf-8") as f:
            brut = f.read()
        assert "\\u00e9" in brut and "é" not in brut

    def test_chemin_de_sortie_absolu(self, tmp_path):
        p = json_builder.build_single_source_json(
            _source(), "UTC", None, str(tmp_path), "s.json")
        assert os.path.isabs(p) and os.path.isfile(p)


class TestCommandeInjection:
    """La ligne écrite au .bat doit résister à un `case.xml` piégé.

    Le nom du cas et l'utilisateur sont LUS sur le partage, pas saisis : un
    guillemet y refermait la citation et `&` enchaînait une commande arbitraire,
    exécutée au clic sur « Importer » (audit paranoid du 18/09/2026).
    """

    def test_esperluette_du_nom_de_cas_reste_dans_les_guillemets(self):
        cmd = json_builder.import_command(
            r"C:\I.exe", "u", r"D:\Cas", "Dupont & Fils", r"D:\s.json")
        assert '"Dupont & Fils"' in cmd
        # Aucun `&` hors d'une paire de guillemets : cmd.exe ne peut rien enchaîner.
        assert all(seg.count("&") == 0 for seg in cmd.split('"')[::2])

    def test_guillemet_refuse(self):
        import pytest
        with pytest.raises(ValueError):
            json_builder.import_command(
                r"C:\I.exe", "u", r"D:\Cas", 'X" & calc & rem ', r"D:\s.json")

    def test_retour_a_la_ligne_refuse(self):
        import pytest
        with pytest.raises(ValueError):
            json_builder.import_command(
                r"C:\I.exe", "u\ncalc", r"D:\Cas", "X", r"D:\s.json")

    def test_pourcent_double_sinon_cmd_le_developpe(self):
        # `Scellé %2024%` : sans doublement, cmd remplace %2024% AVANT l'exécution
        # et IntellaCmd reçoit un chemin inexistant — en renvoyant 0 (donc [OK]).
        cmd = json_builder.import_one_command(
            r"C:\I.exe", "u", r"D:\Cas", "X",
            r"D:\scripts\X_01_Scelle_%2024%.json", r"D:\logs\X_01.log")
        assert "%%2024%%" in cmd and "%2024%" not in cmd.replace("%%2024%%", "")

    def test_echo_neutralise_les_retours_a_la_ligne(self, tmp_path):
        p = json_builder.write_resilient_bat(
            [("Scellé\r\n@echo mechant", 'rem ok')], str(tmp_path), "b.bat")
        with open(p, encoding="utf-8") as f:
            contenu = f.read()
        # Le nom reste sur UNE ligne : rien n'a été ajouté au .bat comme commande.
        assert not any(l.strip().startswith("@echo mechant")
                       for l in contenu.splitlines())


class TestRacineDeLecteur:
    r"""`X:\` ne doit pas être réduit à `X:`.

    Pour un processus Windows, `X:` désigne le **répertoire courant** du lecteur
    X, pas sa racine : IntellaCmd aurait ciblé un autre dossier que celui
    affiché à l'écran, sans rien signaler (audit paranoid du 18/09/2026).
    """

    def test_racine_conservee(self):
        argv = json_builder.import_argv("i.exe", "u", "X:\\", "Cas", "s.json")
        assert argv[argv.index("-c") + 1] == "X:\\"

    def test_separateur_de_fin_toujours_retire(self):
        argv = json_builder.import_argv("i.exe", "u", r"D:\Cas" + "\\", "Cas",
                                        "s.json")
        assert argv[argv.index("-c") + 1] == r"D:\Cas"
