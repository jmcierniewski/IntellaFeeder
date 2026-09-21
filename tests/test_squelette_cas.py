"""Outil `outils/Squelette_cas/squelette_cas.py` : anonymisation et parcours des sous-cas.

Cet outil est testé comme le reste alors qu'il ne fait pas partie de
l'application, parce qu'il porte une **garantie de confidentialité** : le
squelette qu'il produit est destiné à être lu et diffusé librement. Une
régression y serait silencieuse — le fichier resterait valide, simplement il
contiendrait encore une valeur réelle.

Deux contrats verrouillés ici :

- l'anonymisation est **stable** (une même valeur donne toujours le même alias,
  c'est ce qui garde le `<subcase>` du parent aligné sur le dossier du sous-cas) ;
- elle préserve la **forme** — UNC contre lettre de lecteur, profondeur,
  extension, tailles, options d'indexation — puisque c'est elle, et non les noms,
  que les tests d'IntellaFeeder exercent.
"""

import io
import json
import os
import sys

import pytest

OUTILS = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                      "outils", "Squelette_cas")
if OUTILS not in sys.path:
    sys.path.insert(0, OUTILS)

import squelette_cas as sq  # noqa: E402

B = "\\"

# GDH figé : les noms de cas le portent, et un test qui dépendrait de la minute
# d'exécution serait instable. `RACINE_CP` / `RACINE` / `SOUS(n)` disent la
# convention (compound, cas simple, sous-cas) sans la réécrire à chaque assert.
GDH = "20260101_0000"
RACINE_CP = "CAS_CP_" + GDH
RACINE = "CAS_" + GDH


def SOUS(n):
    return "CAS_CP_{}_{}".format(n, GDH)


def ano(actif=True):
    """Anonymiseur au GDH figé (le nommage des cas en dépend)."""
    return sq.Anonymiseur(actif=actif, gdh=GDH)


# --------------------------------------------------------------------------- #
class TestAnonymiseur:
    def test_alias_stable(self):
        a = ano()
        # Sans `preparer`, le premier cas vu tient lieu de racine (repli).
        assert a.cas("Affaire X") == a.cas("Affaire X") == RACINE
        assert a.cas("Affaire Y") == SOUS(1)
        assert a.user("dupond") == "user1"

    def test_inactif_rend_la_valeur_telle_quelle(self):
        a = ano(actif=False)
        assert a.cas("Affaire X") == "Affaire X"
        assert a.chemin_preuve(B * 2 + "srv" + B + "part" + B + "img.E01") == \
            B * 2 + "srv" + B + "part" + B + "img.E01"

    def test_identifiant_garde_la_forme(self):
        a = ano()
        guid = "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee"
        sortie = a.identifiant(guid)
        assert sortie != guid
        assert len(sortie) == len(guid)
        assert [i for i, c in enumerate(sortie) if c == "-"] == \
               [i for i, c in enumerate(guid) if c == "-"]

    def test_identifiant_deterministe(self):
        assert ano().identifiant("abc-def") == \
               ano().identifiant("abc-def")


class TestCheminPreuve:
    """La forme du chemin est ce que l'outil doit conserver : elle est testée."""

    def test_unc_reste_unc(self):
        a = ano()
        sortie = a.chemin_preuve(B * 2 + "NAS" + B + "part" + B + "dossier" + B + "img.E01")
        assert sortie.startswith(B * 2 + "SERVEUR" + B + "PARTAGE")
        assert sortie.endswith(".E01")

    def test_lettre_de_lecteur_reste_locale(self):
        sortie = ano().chemin_preuve("D:" + B + "Scelles" + B + "cle")
        assert sortie.startswith("D:" + B + "Preuves")
        assert not sortie.startswith(B * 2)

    def test_profondeur_conservee(self):
        a = ano()
        court = a.chemin_preuve("D:" + B + "a" + B + "x.E01")
        long_ = a.chemin_preuve("D:" + B + "a" + B + "b" + B + "c" + B + "x.E01")
        assert long_.count(B) > court.count(B)

    def test_extension_conservee(self):
        a = ano()
        assert a.chemin_preuve("D:" + B + "a" + B + "img.E01").endswith(".E01")
        assert a.chemin_preuve("D:" + B + "a" + B + "dossier").endswith("_2")

    def test_nom_de_fichier_nu_ne_devient_pas_un_chemin(self):
        """``firstPartName`` est un nom, pas un chemin : le confondre fausserait le jeu."""
        sortie = ano().nom_fichier("pc.E01")
        assert B not in sortie and sortie.endswith(".E01")


# --------------------------------------------------------------------------- #
def ecrire(chemin, contenu):
    os.makedirs(os.path.dirname(chemin), exist_ok=True)
    with io.open(chemin, "w", encoding="utf-8") as f:
        f.write(contenu)


def faire_cas(dossier, nom, user="dupond", size=1000, subs=None):
    bloc = ""
    if subs is not None:
        bloc = "  <subcases>\n" + "".join(
            "    <subcase>{}</subcase>\n".format(p) for p in subs) + "  </subcases>\n"
    ecrire(os.path.join(dossier, "case.xml"),
           '<?xml version="1.0" encoding="UTF-8"?>\n'
           '<case version="1.0" id="aaaa-bbbb"{}>\n'
           '  <name>{}</name>\n  <description>affaire confidentielle</description>\n'
           '  <timestamp>1750000000000</timestamp>\n  <lastOpened>1760000000000</lastOpened>\n'
           '  <user>{}</user>\n  <size>{}</size>\n'
           '  <originalVersion>3.0</originalVersion>\n  <caseVersion>4.4.0</caseVersion>\n'
           '{}</case>\n'.format(' compound="true"' if subs is not None else "",
                                nom, user, size, bloc))
    ecrire(os.path.join(dossier, "prefs", "case.prefs"),
           "InitialAuthorizedUsers={},martin\n".format(user))
    return dossier


def options(**kw):
    """`sq.Options` du module (partagée CLI/UI), logs coupés sauf mention."""
    kw.setdefault("logs", "aucun")
    kw.setdefault("max_log_ko", 8)
    kw.setdefault("gdh", GDH)
    return sq.Options(**kw)


@pytest.fixture
def compound(tmp_path):
    """Compound à 2 sous-cas, dont un déclaré mais absent du disque."""
    s1 = faire_cas(str(tmp_path / "src" / "Alpha"), "Perquisition Alpha", size=500)
    absent = str(tmp_path / "src" / "Disparu")
    parent = faire_cas(str(tmp_path / "src" / "Parent"), "Dossier Racine",
                       size=1500, subs=[s1, absent])
    return parent, s1, str(tmp_path / "out")


class TestParcours:
    def test_descend_dans_les_sous_cas(self, compound):
        parent, _s1, out = compound
        anon = ano()
        rapport = sq.copier_cas(parent, out, anon, options())
        assert rapport["compound"] is True
        assert rapport["nom"] == RACINE_CP
        assert [s["etat"] for s in rapport["sous_cas"]] == ["ok", "dossier introuvable"]

    def test_sous_cas_absent_nest_pas_une_erreur(self, compound):
        parent, _s1, out = compound
        sq.copier_cas(parent, out, ano(), options())
        assert os.path.isfile(os.path.join(out, RACINE_CP, "case.xml"))
        assert os.path.isfile(os.path.join(out, SOUS(1), "case.xml"))

    def test_alias_du_parent_et_du_dossier_concordent(self, compound):
        """Le `<subcase>` écrit chez le parent doit pointer sur le dossier produit."""
        parent, _s1, out = compound
        sq.copier_cas(parent, out, ano(), options())
        with io.open(os.path.join(out, RACINE_CP, "case.xml"), encoding="utf-8") as f:
            contenu = f.read()
        assert SOUS(1) in contenu
        assert os.path.isdir(os.path.join(out, SOUS(1)))

    def test_boucle_de_references_sarrete(self, tmp_path):
        """Un compound qui se référence lui-même ne doit pas faire tourner l'outil."""
        chemin = str(tmp_path / "Boucle")
        faire_cas(chemin, "Boucle", subs=[chemin])
        rapport = sq.copier_cas(chemin, str(tmp_path / "out"), ano(), options())
        assert rapport["sous_cas"][0]["etat"] == "deja vu ou trop profond"

    def test_mode_brut_conserve_les_valeurs(self, compound):
        parent, _s1, out = compound
        sq.copier_cas(parent, out, ano(actif=False), options())
        with io.open(os.path.join(out, "Parent", "case.xml"), encoding="utf-8") as f:
            assert "Dossier Racine" in f.read()


class TestNommageGDH:
    """Noms de cas : ``CAS_CP_<gdh>``, ``CAS_CP_<n>_<gdh>``, ``CAS_<gdh>``.

    Le GDH est **le même pour tout un compound** : c'est ce qui rattache un
    sous-cas à la fabrication dont il provient et distingue deux squelettes du
    même cas. Le préfixe, lui, se lit sur la racine — d'où ``preparer``.
    """

    def test_compound_et_ses_sous_cas(self, compound):
        parent, _s1, out = compound
        rapport = sq.copier_cas(parent, out, ano(), options())
        assert rapport["nom"] == RACINE_CP
        # Le sous-cas joignable prend 1 ; l'absent est quand meme numerote (2),
        # sinon le <subcase> du parent pointerait dans le vide.
        assert rapport["sous_cas"][0]["nom"] == SOUS(1)
        assert os.path.isdir(os.path.join(out, RACINE_CP))
        assert os.path.isdir(os.path.join(out, SOUS(1)))

    def test_cas_simple(self, tmp_path):
        chemin = faire_cas(str(tmp_path / "seul"), "Cas isolé")
        rapport = sq.copier_cas(chemin, str(tmp_path / "out"), ano(), options())
        assert rapport["nom"] == RACINE          # CAS_<gdh>, sans CP

    def test_gdh_identique_pour_tous_les_elements(self, compound):
        parent, _s1, out = compound
        rapport = sq.copier_cas(parent, out, ano(), options())
        noms = [rapport["nom"]] + [s.get("nom", "") for s in rapport["sous_cas"]]
        assert all(n.endswith(GDH) for n in noms if n)

    def test_gdh_par_defaut_est_l_heure_locale(self):
        """Heure locale (Romance Standard Time ici), jamais UTC."""
        import datetime
        attendu = datetime.datetime.now().strftime(sq.FORMAT_GDH)
        # La minute peut tourner entre les deux appels : on compare le jour.
        assert sq.Anonymiseur().gdh[:8] == attendu[:8]
        assert len(sq.Anonymiseur().gdh) == len("AAAAMMJJ_HHMM")

    def test_deux_fabrications_se_distinguent(self, compound):
        """Deux squelettes du meme cas ne doivent pas porter les memes noms."""
        parent, _s1, out = compound
        r1 = sq.copier_cas(parent, os.path.join(out, "a"),
                           sq.Anonymiseur(gdh="20260101_0000"), options())
        r2 = sq.copier_cas(parent, os.path.join(out, "b"),
                           sq.Anonymiseur(gdh="20260102_1200"), options())
        assert r1["nom"] != r2["nom"]

    def test_mode_brut_ignore_le_gdh(self, compound):
        """En brut on garde les vrais noms : le GDH n'a rien a y faire."""
        parent, _s1, out = compound
        rapport = sq.copier_cas(parent, out, ano(actif=False), options())
        assert rapport["nom"] == "Dossier Racine"

    def test_preparer_lit_le_type_sur_la_racine(self, compound):
        parent, s1, _out = compound
        a = ano()
        a.preparer(parent)
        assert a.compound is True and a.cas("Dossier Racine") == RACINE_CP
        b = ano()
        b.preparer(s1)                            # un sous-cas pris pour racine
        assert b.compound is False and b.cas("Perquisition Alpha") == RACINE


class TestSqueletteUtilisable:
    """Le squelette doit servir de banc d'essai, pas seulement exister.

    Regression verrouillee : les `<subcase>` etaient ecrits vers un chemin
    fictif absolu (`D:` + antislash + `SquelettesTest`), si bien que TOUS les sous-cas du
    squelette etaient injoignables — le banc d'essai ne pouvait exercer que le
    chemin degrade, jamais le nominal.
    """

    def test_les_sous_cas_du_squelette_sont_joignables(self, compound):
        parent, _s1, out = compound
        sq.fabriquer(sq.Options(cas=parent, sortie=out, logs="aucun", gdh=GDH))
        import case_meta
        meta = case_meta.read_case(os.path.join(out, RACINE_CP))
        assert meta["is_compound"] is True
        etats = [sc["exists"] for sc in meta["subcases"]]
        # Le 1er existait a l'origine, le 2e non : le squelette reproduit les deux.
        assert etats == [True, False]

    def test_subcases_ecrits_en_relatif(self, compound):
        parent, _s1, out = compound
        sq.fabriquer(sq.Options(cas=parent, sortie=out, logs="aucun", gdh=GDH))
        with io.open(os.path.join(out, RACINE_CP, "case.xml"), encoding="utf-8") as f:
            contenu = f.read()
        assert SOUS(1) in contenu
        assert "SquelettesTest" not in contenu

    def test_squelette_portable(self, compound, tmp_path):
        """Deplace ailleurs, le squelette reste lisible."""
        import shutil
        import case_meta
        parent, _s1, out = compound
        sq.fabriquer(sq.Options(cas=parent, sortie=out, logs="aucun", gdh=GDH))
        ailleurs = str(tmp_path / "ailleurs")
        shutil.copytree(out, ailleurs)
        meta = case_meta.read_case(os.path.join(ailleurs, RACINE_CP))
        assert meta["subcases"][0]["exists"] is True


class TestVerificationAnonymat:
    def test_aucune_fuite_sur_un_squelette_normal(self, compound):
        parent, _s1, out = compound
        anon = ano()
        sq.copier_cas(parent, out, anon, options())
        assert sq.verifier_anonymat(out, anon) == []

    def test_une_valeur_oubliee_est_detectee(self, compound):
        parent, _s1, out = compound
        anon = ano()
        sq.copier_cas(parent, out, anon, options())
        ecrire(os.path.join(out, RACINE_CP, "oubli.txt"), "Dossier Racine")
        fuites = sq.verifier_anonymat(out, anon)
        assert len(fuites) == 1 and "oubli.txt" in fuites[0]

    def test_un_nom_de_fichier_qui_trahit_est_detecte(self, compound):
        """`IF_<cas>.info` a montré qu'un nom de fichier fuit aussi bien qu'un contenu."""
        parent, _s1, out = compound
        anon = ano()
        sq.copier_cas(parent, out, anon, options())
        ecrire(os.path.join(out, RACINE_CP, "IF_Dossier Racine.info"), "{}")
        fuites = sq.verifier_anonymat(out, anon)
        assert any("nom :" in f for f in fuites)


class TestFichiersAnnexes:
    def test_info_renomme_et_chemins_substitues(self, compound):
        parent, s1, out = compound
        ecrire(os.path.join(s1, "IF_Perquisition Alpha.info"), json.dumps(
            {"folder_sizes": {"d:" + B + B + "scelles" + B + B + "cle": 42},
             "skip_integrity_check": True}))
        anon = ano()
        sq.copier_cas(parent, out, anon, options())
        produit = os.path.join(out, SOUS(1), "IF_{}.info".format(SOUS(1)))
        assert os.path.isfile(produit)
        with io.open(produit, encoding="utf-8") as f:
            data = json.load(f)
        assert data["skip_integrity_check"] is True
        assert all("scelles" not in k for k in data["folder_sizes"])

    def test_sources_xml_garde_tailles_et_options(self, compound):
        parent, s1, out = compound
        ecrire(os.path.join(s1, "sources.xml"),
               '<?xml version="1.0" encoding="UTF-8"?>\n<sources>\n'
               '  <caseName>Perquisition Alpha</caseName>\n'
               '  <source>\n    <name>PC saisi</name>\n    <type>Disk Image</type>\n'
               '    <size>1000</size>\n    <totalSize>4000</totalSize>\n'
               '    <partsCount>4</partsCount>\n    <timeZone>UTC</timeZone>\n'
               '    <firstPartName>pc.E01</firstPartName>\n'
               '    <indexOptions><indexArchives>true</indexArchives></indexOptions>\n'
               '    <path>D:' + B + 'Scelles' + B + 'pc.E01</path>\n'
               '  </source>\n</sources>\n')
        anon = ano()
        sq.copier_cas(parent, out, anon, options())
        with io.open(os.path.join(out, SOUS(1), "sources.xml"), encoding="utf-8") as f:
            contenu = f.read()
        # La forme utile est conservee...
        for garde in ("<totalSize>4000", "<partsCount>4", "<timeZone>UTC",
                      "<indexArchives>true"):
            assert garde in contenu
        # ...les valeurs nominatives, non.
        assert "PC saisi" not in contenu and "Perquisition Alpha" not in contenu
        assert "SOURCE_1" in contenu

    def test_tasks2_anonymise_les_noms_pas_la_structure(self, compound):
        parent, s1, out = compound
        ecrire(os.path.join(s1, "prefs", "tasks2.json"), json.dumps(
            [{"id": "1111-2222", "name": "OCR affaire", "condition": "ALL_ITEMS_CONDITION"}]))
        sq.copier_cas(parent, out, ano(), options())
        with io.open(os.path.join(out, SOUS(1), "prefs", "tasks2.json"), encoding="utf-8") as f:
            taches = json.load(f)
        assert taches[0]["name"] == "Tache 1"
        assert taches[0]["condition"] == "ALL_ITEMS_CONDITION"


class TestLogs:
    def test_inventaire_ne_copie_rien(self, compound):
        parent, s1, out = compound
        ecrire(os.path.join(s1, "logs", "case-main-2026-09-01.log"), "ligne 1\nligne 2\n")
        rapport = sq.copier_cas(parent, out, ano(), options(logs="inventaire"))
        releve = rapport["sous_cas"][0]["logs"]
        assert releve and releve[0]["lignes"] == 2
        assert not os.path.isdir(os.path.join(out, SOUS(1), "logs"))

    def test_copie_tronquee(self, compound):
        parent, s1, out = compound
        ecrire(os.path.join(s1, "logs", "gros.log"), "x" * 50_000)
        sq.copier_cas(parent, out, ano(actif=False),
                      options(logs="brut", max_log_ko=1))
        produit = os.path.join(out, "Alpha", "logs", "gros.log")
        assert os.path.getsize(produit) < 2 * 1024


class TestGardeFousPartages:
    """`valider` et `fabriquer` sont le seul chemin des DEUX interfaces.

    C'est ce qui interdit a l'UI de desserrer un controle que le CLI applique :
    si ces tests passent, les deux se comportent pareil par construction.
    """

    def test_logs_brut_refuse_sans_mode_brut(self, compound):
        parent, _s1, out = compound
        refus = sq.valider(sq.Options(cas=parent, sortie=out, logs="brut"))
        assert refus and "brut" in refus.lower()

    def test_logs_brut_accepte_avec_mode_brut(self, compound):
        parent, _s1, out = compound
        assert sq.valider(sq.Options(cas=parent, sortie=out, logs="brut",
                                     brut=True)) == ""

    def test_refuse_un_dossier_sans_case_xml(self, tmp_path):
        vide = tmp_path / "vide"
        vide.mkdir()
        refus = sq.valider(sq.Options(cas=str(vide), sortie=str(tmp_path / "o")))
        assert "case.xml" in refus

    def test_refuse_une_sortie_non_vide(self, compound):
        parent, _s1, out = compound
        os.makedirs(out, exist_ok=True)
        ecrire(os.path.join(out, "x.txt"), "x")
        assert "non vide" in sq.valider(sq.Options(cas=parent, sortie=out))
        assert sq.valider(sq.Options(cas=parent, sortie=out, force=True)) == ""

    def test_refuse_une_sortie_vide_de_nom(self, compound):
        parent, _s1, _out = compound
        assert sq.valider(sq.Options(cas=parent, sortie="")) != ""

    def test_fabriquer_verifie_toujours_l_anonymat(self, compound):
        """La verification ne doit pas pouvoir etre sautee par un appelant."""
        parent, _s1, out = compound
        rapport, fuites = sq.fabriquer(sq.Options(cas=parent, sortie=out, logs="aucun", gdh=GDH))
        assert rapport["nom"] == RACINE_CP and fuites == []
        assert os.path.isfile(os.path.join(out, sq.MANIFESTE))

    def test_fabriquer_en_brut_ne_verifie_pas(self, compound):
        parent, _s1, out = compound
        rapport, fuites = sq.fabriquer(
            sq.Options(cas=parent, sortie=out, brut=True, logs="aucun", gdh=GDH))
        assert fuites == [] and rapport["nom"] == "Dossier Racine"


class TestLigneDeCommande:
    def test_logs_brut_refuse_hors_mode_brut(self, compound, capsys):
        parent, _s1, out = compound
        code = sq.main([parent, out, "--logs", "brut"])
        assert code == 2
        assert "brut" in capsys.readouterr().err.lower()

    def test_refuse_un_dossier_qui_nest_pas_un_cas(self, tmp_path, capsys):
        vide = tmp_path / "vide"
        vide.mkdir()
        assert sq.main([str(vide), str(tmp_path / "out")]) == 2
        assert "case.xml" in capsys.readouterr().err

    def test_refuse_une_sortie_non_vide_sans_force(self, compound, capsys):
        parent, _s1, out = compound
        os.makedirs(out, exist_ok=True)
        ecrire(os.path.join(out, "deja_la.txt"), "x")
        assert sq.main([parent, out]) == 2
        assert "--force" in capsys.readouterr().err

    def test_parcours_complet_ecrit_le_manifeste(self, compound):
        parent, _s1, out = compound
        assert sq.main([parent, out]) == 0
        with io.open(os.path.join(out, sq.MANIFESTE), encoding="utf-8") as f:
            manifeste = f.read()
        assert "anonymisé" in manifeste
        assert "Aucune valeur d'origine" in manifeste

    def test_mode_brut_avertit_dans_le_manifeste(self, compound):
        parent, _s1, out = compound
        assert sq.main([parent, out, "--brut"]) == 0
        with io.open(os.path.join(out, sq.MANIFESTE), encoding="utf-8") as f:
            assert "données réelles" in f.read()
