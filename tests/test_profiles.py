"""Profils d'analyse : CRUD sur fichiers, profil « défaut » réservé, collisions.

La collision de noms est le bug corrigé au lot 4 : deux noms distincts peuvent
s'assainir vers le même fichier (``a:b`` et ``a/b`` → ``a_b.json``), ce qui
écrasait un profil sans rien dire.
"""

import json
import os

import pytest

import config
import profile_catalog as pc
import profiles


@pytest.fixture
def profils(tmp_path, monkeypatch):
    """Isole le dossier des profils dans un dossier temporaire."""
    d = tmp_path / "profils"
    d.mkdir()
    monkeypatch.setattr(config, "profiles_dir", lambda: str(d))
    return d


def _valeurs(**over):
    vals = pc.default_values()
    vals.update(over)
    return vals


class TestCrud:
    def test_liste_vide_contient_defaut(self, profils):
        assert profiles.list_names() == [profiles.DEFAULT_NAME]

    def test_creation_et_relecture(self, profils):
        cle = "indexArchives"
        profiles.save_profile("Rapide", _valeurs(**{cle: not pc.OPTIONS[cle]["default"]}), "sans archives")
        assert "Rapide" in profiles.list_names()
        assert profiles.get_values("Rapide")[cle] != pc.OPTIONS[cle]["default"]
        assert profiles.get_comment("Rapide") == "sans archives"

    def test_seules_les_differences_sont_stockees(self, profils):
        cle = "indexArchives"
        profiles.save_profile("Rapide", _valeurs(**{cle: not pc.OPTIONS[cle]["default"]}))
        contenu = json.loads((profils / "Rapide.json").read_text(encoding="utf-8"))
        assert list(contenu["options"]) == [cle]

    def test_tri_insensible_a_la_casse_defaut_en_tete(self, profils):
        for n in ("zeta", "Alpha"):
            profiles.save_profile(n, _valeurs())
        assert profiles.list_names() == [profiles.DEFAULT_NAME, "Alpha", "zeta"]

    def test_renommage(self, profils):
        profiles.save_profile("Ancien", _valeurs(), "note")
        profiles.rename_profile("Ancien", "Nouveau")
        assert "Nouveau" in profiles.list_names() and "Ancien" not in profiles.list_names()
        assert profiles.get_comment("Nouveau") == "note"

    def test_suppression(self, profils):
        profiles.save_profile("Jetable", _valeurs())
        profiles.delete_profile("Jetable")
        assert "Jetable" not in profiles.list_names()

    def test_fichier_corrompu_ignore(self, profils):
        (profils / "casse.json").write_text("{pas du json", encoding="utf-8")
        assert profiles.list_names() == [profiles.DEFAULT_NAME]

    def test_emit_map(self, profils):
        cle = "indexArchives"
        profiles.save_profile("Rapide", _valeurs(**{cle: not pc.OPTIONS[cle]["default"]}))
        emis = profiles.emit_map({profiles.DEFAULT_NAME, "Rapide"})
        assert emis[profiles.DEFAULT_NAME] == {}
        assert cle in emis["Rapide"]


class TestDefautReserve:
    def test_enregistrement_refuse(self, profils):
        with pytest.raises(ValueError):
            profiles.save_profile(profiles.DEFAULT_NAME, _valeurs())

    def test_suppression_refusee(self, profils):
        with pytest.raises(ValueError):
            profiles.delete_profile(profiles.DEFAULT_NAME)

    def test_renommage_refuse(self, profils):
        with pytest.raises(ValueError):
            profiles.rename_profile(profiles.DEFAULT_NAME, "Autre")

    def test_nom_vide_refuse(self, profils):
        with pytest.raises(ValueError):
            profiles.save_profile("   ", _valeurs())

    def test_valeurs_du_defaut_sont_les_defauts(self, profils):
        assert profiles.get_values(profiles.DEFAULT_NAME) == pc.default_values()


class TestCollisionDeNoms:
    def test_ecrasement_silencieux_refuse(self, profils):
        """Régression lot 4 : « a:b » puis « a/b » écrasaient le même fichier."""
        profiles.save_profile("a:b", _valeurs(), "premier")
        with pytest.raises(ValueError) as exc:
            profiles.save_profile("a/b", _valeurs(), "second")
        assert "a:b" in str(exc.value)
        # Le profil d'origine est intact.
        assert profiles.get_comment("a:b") == "premier"
        assert profiles.list_names() == [profiles.DEFAULT_NAME, "a:b"]

    def test_mise_a_jour_du_meme_profil_autorisee(self, profils):
        profiles.save_profile("Rapide", _valeurs(), "v1")
        profiles.save_profile("Rapide", _valeurs(), "v2")
        assert profiles.get_comment("Rapide") == "v2"

    def test_renommage_vers_un_nom_en_collision_refuse(self, profils):
        profiles.save_profile("a:b", _valeurs())
        profiles.save_profile("Autre", _valeurs())
        with pytest.raises(ValueError):
            profiles.rename_profile("Autre", "a/b")
        assert profiles.exists("Autre")


class TestLibelleAffiche:
    """« défaut » reste l'IDENTIFIANT, « Défaut Intella » n'est que l'affichage.

    Le renommer pour de bon casserait la correspondance entre onglets, les
    listes de sources exportées et les fichiers `.ini` déjà écrits.
    """
    def test_defaut_saffiche_autrement(self):
        assert profiles.display_name(profiles.DEFAULT_NAME) == "Défaut Intella"
        assert profiles.DEFAULT_NAME == "défaut"

    def test_les_autres_profils_gardent_leur_nom(self):
        assert profiles.display_name("Rapide") == "Rapide"

    def test_aller_retour(self):
        for nom in (profiles.DEFAULT_NAME, "Rapide", "Défaut Intella maison"):
            assert profiles.internal_name(profiles.display_name(nom)) == nom


class TestDuplication:
    def test_copie_valeurs_et_commentaire(self, profils):
        profiles.save_profile("Source", _valeurs(indexArchives=False), "mon essai")
        profiles.duplicate_profile("Source", "Copie")
        assert profiles.exists("Copie")
        assert profiles.get_comment("Copie") == "mon essai"
        assert profiles.get_values("Copie")["indexArchives"] is False

    def test_dupliquer_le_defaut_est_permis(self, profils):
        """C'est le point de départ le plus courant : partir des réglages Intella."""
        profiles.duplicate_profile(profiles.DEFAULT_NAME, "Depuis défaut")
        assert profiles.exists("Depuis défaut")
        assert profiles.get_values("Depuis défaut") == pc.default_values()

    def test_nom_deja_pris_refuse(self, profils):
        profiles.save_profile("Existant", _valeurs())
        with pytest.raises(ValueError):
            profiles.duplicate_profile("Existant", "Existant")

    def test_source_inconnue_refusee(self, profils):
        with pytest.raises(ValueError):
            profiles.duplicate_profile("Fantôme", "Copie")

    def test_nom_vide_refuse(self, profils):
        profiles.save_profile("Source", _valeurs())
        with pytest.raises(ValueError):
            profiles.duplicate_profile("Source", "   ")
