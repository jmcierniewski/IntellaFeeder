"""Utilitaires transverses : assainissement des noms, tailles lisibles, i18n.

``sanitize_filename`` est aussi la source de la collision de noms de profils
connue (deux noms distincts peuvent produire le même fichier) — le test
documente le comportement actuel.
"""

import os

import config
import i18n


class TestSanitizeFilename:
    def test_caracteres_interdits_remplaces(self):
        assert config.sanitize_filename('a<b>c:d"e/f\\g|h?i*j') == "a_b_c_d_e_f_g_h_i_j"

    def test_espaces_remplaces(self):
        assert config.sanitize_filename("Cas de test") == "Cas_de_test"

    def test_points_et_espaces_de_bord_retires(self):
        assert config.sanitize_filename("  .Cas.  ") == "Cas"

    def test_vide_donne_case(self):
        assert config.sanitize_filename("") == "Case"
        assert config.sanitize_filename(None) == "Case"

    def test_accents_conserves(self):
        assert config.sanitize_filename("Scellé") == "Scellé"

    def test_collision_connue(self):
        """Limite documentée : « a:b » et « a/b » donnent le même nom de fichier.

        Conséquence côté profils = écrasement silencieux (à corriger lot 4)."""
        assert config.sanitize_filename("a:b") == config.sanitize_filename("a/b")


class TestHumanSize:
    def test_go_au_dela_de_1_go(self):
        assert config.human_size(2 * config.GB).startswith("2.00")

    def test_mo_en_dessous(self):
        assert config.human_size(5 * 1024 ** 2).startswith("5.0")

    def test_zero(self):
        assert config.human_size(0).startswith("0.0")


class TestCaseDirs:
    def test_scripts_et_logs_sous_le_cas(self):
        cas = config.case_dir("Mon Cas")
        assert config.case_scripts_dir("Mon Cas").startswith(cas + os.sep)
        assert config.case_logs_dir("Mon Cas").startswith(cas + os.sep)

    def test_nom_assaini_dans_le_chemin(self):
        assert "Mon_Cas" in config.case_dir("Mon Cas")


class TestEpochMsToStr:
    def test_zero_donne_tiret(self):
        assert config.epoch_ms_to_str(0) == "—"

    def test_horodatage_formate(self):
        assert len(config.epoch_ms_to_str(1_700_000_000_000)) == len("2023-11-14 22:13")


class TestI18n:
    def test_repli_sur_le_texte_francais(self):
        """Une clé inconnue rend le défaut FR passé à l'appel."""
        assert i18n.t("cle.qui.nexiste.pas", "texte de repli") == "texte de repli"

    def test_langues_disponibles_contiennent_fr_et_us(self):
        codes = i18n.available_languages()
        assert "FR" in codes and "US" in codes

    def test_chargement_langue(self):
        i18n.load("US")
        assert i18n.t("import.compute_size", "Calculer la taille") == "Compute size"
        i18n.load("FR")
        assert i18n.t("import.compute_size", "x") == "Calculer la taille"

    def test_pas_de_pollution_entre_langues(self):
        """Chaque load() remplace intégralement l'état (pas de fusion)."""
        i18n.load("US")
        us = i18n.t("import.summarize", "?")
        i18n.load("FR")
        fr = i18n.t("import.summarize", "?")
        assert us != fr

    def test_formatage_des_parametres(self):
        assert "42" in i18n.t("cle.absente", "valeur = {n}", n=42)
