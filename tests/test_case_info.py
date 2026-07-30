"""Fichier ``IF_<cas>.info`` : cache des tailles + réglage d'intégrité.

Contrat v2.5g : le cache est la mémoire des tailles entre sessions. Une clé mal
normalisée (casse, séparateur final) provoquerait un rescan inutile — ou pire,
une taille attribuée au mauvais chemin.
"""

import json
import os

import case_info


class TestReadWrite:
    def test_defaut_si_fichier_absent(self, tmp_case):
        folder, name = tmp_case
        data = case_info.read_info(folder, name)
        assert data["folder_sizes"] == {} and data["skip_integrity_check"] is True

    def test_aller_retour(self, tmp_case):
        folder, name = tmp_case
        assert case_info.write_info(folder, name, {"folder_sizes": {"d:\\a": 5}}) is True
        assert case_info.read_info(folder, name)["folder_sizes"] == {"d:\\a": 5}

    def test_nom_de_fichier_assaini(self, tmp_case):
        folder, _ = tmp_case
        case_info.write_info(folder, "Cas / interdit : *?", {})
        fichiers = [f for f in os.listdir(folder) if f.endswith(".info")]
        assert len(fichiers) == 1
        assert not set('/\\:*?"<>|') & set(fichiers[0])

    def test_fichier_corrompu_ne_leve_pas(self, tmp_case):
        folder, name = tmp_case
        with open(case_info.info_path(folder, name), "w", encoding="utf-8") as f:
            f.write("{ ceci n'est pas du JSON")
        assert case_info.read_info(folder, name)["folder_sizes"] == {}

    def test_folder_sizes_de_mauvais_type_corrige(self, tmp_case):
        folder, name = tmp_case
        with open(case_info.info_path(folder, name), "w", encoding="utf-8") as f:
            json.dump({"folder_sizes": "pas un dict"}, f)
        assert case_info.read_info(folder, name)["folder_sizes"] == {}

    def test_dossier_inexistant_renvoie_false(self, tmp_path):
        assert case_info.write_info(str(tmp_path / "absent"), "X", {}) is False


class TestFolderSizes:
    def test_cle_normalisee(self, tmp_case):
        """Casse et séparateur final ne doivent pas créer deux entrées."""
        folder, name = tmp_case
        case_info.update_folder_sizes(folder, name, {"D:\\Cas\\Source\\": 100})
        cache = case_info.get_folder_sizes(folder, name)
        assert cache == {"d:\\cas\\source": 100}

    def test_fusion_sans_ecrasement_des_autres(self, tmp_case):
        folder, name = tmp_case
        case_info.update_folder_sizes(folder, name, {"D:\\a": 1})
        case_info.update_folder_sizes(folder, name, {"D:\\b": 2})
        assert case_info.get_folder_sizes(folder, name) == {"d:\\a": 1, "d:\\b": 2}

    def test_remesure_ecrase_la_valeur(self, tmp_case):
        folder, name = tmp_case
        case_info.update_folder_sizes(folder, name, {"D:\\a": 1})
        case_info.update_folder_sizes(folder, name, {"d:\\A": 99})
        assert case_info.get_folder_sizes(folder, name) == {"d:\\a": 99}

    def test_valeurs_entieres(self, tmp_case):
        folder, name = tmp_case
        case_info.update_folder_sizes(folder, name, {"D:\\a": "1234"})
        assert case_info.get_folder_sizes(folder, name)["d:\\a"] == 1234

    def test_conserve_le_reglage_integrite(self, tmp_case):
        folder, name = tmp_case
        case_info.set_skip_integrity(folder, name, False)
        case_info.update_folder_sizes(folder, name, {"D:\\a": 1})
        assert case_info.get_skip_integrity(folder, name) is False


class TestSkipIntegrity:
    def test_defaut_vrai(self, tmp_case):
        folder, name = tmp_case
        assert case_info.get_skip_integrity(folder, name) is True

    def test_aller_retour(self, tmp_case):
        folder, name = tmp_case
        case_info.set_skip_integrity(folder, name, False)
        assert case_info.get_skip_integrity(folder, name) is False

    def test_conserve_le_cache_des_tailles(self, tmp_case):
        folder, name = tmp_case
        case_info.update_folder_sizes(folder, name, {"D:\\a": 7})
        case_info.set_skip_integrity(folder, name, False)
        assert case_info.get_folder_sizes(folder, name) == {"d:\\a": 7}
