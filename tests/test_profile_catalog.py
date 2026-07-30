"""Catalogue d'options de profil : contrat « défaut = option omise ».

Piège documenté (bug v2.4b) : ``sourceTypeFilter`` sans ``sourceTypeFilterMode``
fait échouer IntellaCmd (« Missing source type filter mode »). Le mode vaut
souvent le défaut, donc le diff l'omettrait — il doit être ré-ajouté.
"""

import config
import profile_catalog as pc


class TestDefaultValues:
    def test_toutes_les_options_presentes(self):
        assert set(pc.default_values()) == set(pc.OPTIONS)

    def test_snapshot_independant(self):
        """Chaque appel rend un dict neuf : modifier l'un ne contamine pas l'autre."""
        d = pc.default_values()
        d["indexArchives"] = "modifié"
        assert pc.default_values()["indexArchives"] != "modifié"


class TestCoerce:
    def test_bool_depuis_texte(self):
        for vrai in ("true", "True", "1", "oui", "vrai", "yes"):
            assert pc.coerce("indexArchives", vrai) is True
        for faux in ("false", "0", "non", "", "n'importe quoi"):
            assert pc.coerce("indexArchives", faux) is False

    def test_int_invalide_retombe_sur_defaut(self):
        defaut = pc.OPTIONS["numberMessagesPerConversation"]["default"]
        assert pc.coerce("numberMessagesPerConversation", "abc") == defaut
        assert pc.coerce("numberMessagesPerConversation", " 42 ") == 42

    def test_cle_inconnue_renvoyee_telle_quelle(self):
        assert pc.coerce("cleQuiNexistePas", "xyz") == "xyz"

    def test_none_devient_chaine_vide(self):
        assert pc.coerce("sourceTypeFilter", None) == ""


class TestDiffFromDefault:
    def test_valeurs_par_defaut_omises(self):
        assert pc.diff_from_default(pc.default_values()) == {}

    def test_seules_les_differences_emises(self):
        vals = pc.default_values()
        cle = "indexArchives"
        vals[cle] = not pc.OPTIONS[cle]["default"]
        assert pc.diff_from_default(vals) == {cle: vals[cle]}

    def test_chaine_vide_omise(self):
        vals = pc.default_values()
        vals["sourceTypeFilter"] = "   "
        assert "sourceTypeFilter" not in pc.diff_from_default(vals)

    def test_filtre_mime_force_son_mode(self):
        """Régression v2.4b : le mode doit accompagner le filtre, même au défaut."""
        vals = pc.default_values()
        vals["sourceTypeFilter"] = "application/pdf"
        emit = pc.diff_from_default(vals)
        assert emit["sourceTypeFilter"] == "application/pdf"
        assert emit["sourceTypeFilterMode"]

    def test_mode_explicite_conserve(self):
        vals = pc.default_values()
        vals["sourceTypeFilter"] = "application/pdf"
        vals["sourceTypeFilterMode"] = "include"
        assert pc.diff_from_default(vals)["sourceTypeFilterMode"] == "include"

    def test_cles_hors_catalogue_ignorees(self):
        vals = pc.default_values()
        vals["optionInventee"] = True
        assert "optionInventee" not in pc.diff_from_default(vals)


class TestOptionsForSource:
    def _valeurs_avec_option_image(self):
        cle = sorted(pc.IMAGE_ONLY_KEYS)[0]
        vals = pc.default_values()
        opt = pc.OPTIONS[cle]
        vals[cle] = (not opt["default"]) if opt["type"] == "bool" else "valeur_test"
        return cle, vals

    def test_options_image_retirees_pour_un_dossier(self):
        cle, vals = self._valeurs_avec_option_image()
        emit = pc.options_for_source(vals, config.SOURCE_TYPE_FOLDER)
        assert cle not in emit

    def test_options_image_conservees_pour_une_image(self):
        cle, vals = self._valeurs_avec_option_image()
        emit = pc.options_for_source(vals, config.SOURCE_TYPE_DISK_IMAGE)
        assert cle in emit

    def test_image_only_keys_non_vide(self):
        assert pc.IMAGE_ONLY_KEYS, "le filtrage image n'aurait plus rien à filtrer"
