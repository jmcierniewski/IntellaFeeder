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
        brut = open(p, encoding="utf-8").read()
        assert "\\u00e9" in brut and "é" not in brut

    def test_chemin_de_sortie_absolu(self, tmp_path):
        p = json_builder.build_single_source_json(
            _source(), "UTC", None, str(tmp_path), "s.json")
        assert os.path.isabs(p) and os.path.isfile(p)
