"""Référentiel des types MIME : parsing `.properties`, 3 états, apprentissage.

Ce qui est verrouillé ici tient à deux constats faits sur des exports réels
(09/09/2026) et qui ne se devinent pas :

- la **clé vide** du référentiel (``=Untyped``) est un type filtrable, pas une
  ligne parasite — le `,,` des filtres Intella la désigne ;
- **121 noms d'un filtre réel ne sont pas décrits** par le fichier livré (ce
  sont des alias : ``application/msword`` quand le référentiel ne décrit que
  ``application/vnd.ms-word``). D'où trois états, et pas deux : les traiter
  comme des erreurs ferait 121 fausses alertes sur une seule source.
"""

import os

import pytest

import config
import mime_catalog as mc
import mime_data


@pytest.fixture
def mimes(tmp_path, monkeypatch):
    """Isole ``mimetypes\\`` **et** neutralise le référentiel embarqué.

    Sans cette seconde partie, chaque test partirait des 679 descriptions et
    800 noms livrés dans `mime_data` : les assertions porteraient sur un état
    qui change à chaque régénération du module. La fusion embarqué + externe a
    ses propres tests, plus bas.
    """
    d = tmp_path / "mimetypes"
    d.mkdir()
    monkeypatch.setattr(config, "mime_dir", lambda: str(d))
    monkeypatch.setattr(mime_data, "DESCRIPTIONS", {})
    monkeypatch.setattr(mime_data, "OBSERVED", [])
    mc.load()
    return d


def _ecrire(dossier, nom, contenu, encodage="latin-1"):
    chemin = os.path.join(str(dossier), nom)
    with open(chemin, "w", encoding=encodage) as fh:
        fh.write(contenu)
    return chemin


# --- Parsing du format .properties ----------------------------------------

def test_parse_cle_vide_est_un_type():
    """``=Untyped`` : la clé vide est conservée, c'est le type « sans type »."""
    data, _ = mc.parse_properties("=Untyped\napplication/pdf=PDF Document\n")
    assert data[""] == "Untyped"
    assert data["application/pdf"] == "PDF Document"


def test_parse_commentaires_et_lignes_vides():
    data, _ = mc.parse_properties("# titre\n\n!autre commentaire\na/b=Truc\n")
    assert data == {"a/b": "Truc"}


def test_parse_doublons_rendus_a_lappelant():
    """Dernière valeur gagnante (comme Java), mais le doublon est signalé."""
    data, doublons = mc.parse_properties("a/b=Un\na/b=Deux\n")
    assert data["a/b"] == "Deux"
    assert doublons == ["a/b"]


def test_parse_separateur_deux_points_et_unicode():
    data, _ = mc.parse_properties("a/b:Caf\\u00e9\n")
    assert data["a/b"] == "Café"


def test_parse_ligne_de_continuation():
    data, _ = mc.parse_properties("a/b=Un libelle \\\ncoupe en deux\n")
    assert data["a/b"] == "Un libelle coupe en deux"


def test_parse_ligne_sans_separateur_ignoree():
    data, _ = mc.parse_properties("ligne sans separateur\na/b=Ok\n")
    assert data == {"a/b": "Ok"}


# --- Découpage d'un filtre -------------------------------------------------

def test_split_filter_garde_la_cle_vide_une_seule_fois():
    """Le ``,,`` des exports Intella désigne « Untyped » — ne pas l'effacer."""
    assert mc.split_filter("a/b,,c/d,,") == ["a/b", "", "c/d"]


def test_split_filter_conserve_l_ordre_et_dedoublonne():
    assert mc.split_filter("b, a , b") == ["b", "a"]


def test_split_filter_vide():
    assert mc.split_filter("") == [""]


# --- Trois états -----------------------------------------------------------

def test_trois_etats(mimes):
    _ecrire(mimes, "descr.properties", "a/decrit=Un type\n")
    mc.load()
    mc.learn(["a/observe"])
    assert mc.status("a/decrit") == mc.STATUS_DESCRIBED
    assert mc.status("a/observe") == mc.STATUS_OBSERVED
    assert mc.status("a/jamais-vu") == mc.STATUS_UNKNOWN


def test_alias_non_decrit_reste_valide(mimes):
    """Le cas réel : un alias qu'Intella écrit mais ne décrit pas."""
    _ecrire(mimes, "descr.properties", "application/vnd.ms-word=Word 97-2003\n")
    mc.load()
    mc.learn(["application/msword", "application/winword"])
    assert mc.status("application/msword") == mc.STATUS_OBSERVED
    assert mc.label("application/msword") is None
    # …et il n'est PAS compté comme inconnu dans un filtre.
    resume = mc.summarize_filter("application/vnd.ms-word,application/msword")
    assert resume == {mc.STATUS_DESCRIBED: 1, mc.STATUS_OBSERVED: 1,
                      mc.STATUS_UNKNOWN: 0, mc.STATUS_USER: 0, "total": 2}


def test_describe_replis(mimes):
    _ecrire(mimes, "descr.properties", "=Untyped\na/b=Le libelle\n")
    mc.load()
    assert mc.describe("a/b") == "Le libelle"
    assert mc.describe("") == "Untyped"          # libellé du référentiel
    assert mc.describe("x/y") == "x/y"           # repli sur le nom


def test_describe_cle_vide_sans_referentiel(mimes):
    """Sans référentiel, la ligne du type vide doit rester visible."""
    assert mc.describe("") == "(sans type)"


def test_classify_filter(mimes):
    _ecrire(mimes, "descr.properties", "a/b=Le libelle\n")
    mc.load()
    assert mc.classify_filter("a/b,x/y") == [
        ("a/b", mc.STATUS_DESCRIBED, "Le libelle"),
        ("x/y", mc.STATUS_UNKNOWN, "x/y"),
    ]


# --- Catégories : la matière du sélecteur ----------------------------------

def test_categories_triees_par_libelle(mimes):
    _ecrire(mimes, "d.properties",
            "category/zeta=Alpha\ncategory/alpha=Zeta\napplication/pdf=PDF\n")
    mc.load()
    assert mc.categories() == [("category/zeta", "Alpha"), ("category/alpha", "Zeta")]


def test_categories_incluent_les_observees_non_decrites(mimes):
    mc.learn(["category/inedite", "application/x"])
    assert ("category/inedite", "category/inedite") in mc.categories()


def test_filter_is_only_categories(mimes):
    assert mc.filter_is_only_categories("category/a,category/b") is True
    assert mc.filter_is_only_categories("category/a,application/pdf") is False
    assert mc.filter_is_only_categories("") is False        # rien à représenter
    assert mc.filter_is_only_categories("  ,  ") is False


def test_build_category_filter_ordre_stable(mimes):
    """Deux compositions équivalentes doivent donner la MÊME chaîne.

    Sinon un profil relu paraîtrait modifié parce que l'ordre des cases a
    changé, et « Enregistrer » proposerait une différence qui n'en est pas une.
    """
    _ecrire(mimes, "d.properties", "category/b=Bravo\ncategory/a=Alpha\n")
    mc.load()
    assert mc.build_category_filter(["category/b", "category/a"]) \
        == mc.build_category_filter(["category/a", "category/b"]) \
        == "category/a,category/b"


def test_build_category_filter_ignore_l_inconnu(mimes):
    _ecrire(mimes, "d.properties", "category/a=Alpha\n")
    mc.load()
    assert mc.build_category_filter(["category/a", "category/jamais_vue"]) == "category/a"


# --- Recherche -------------------------------------------------------------

def test_search_porte_sur_le_nom_ET_la_description(mimes):
    """Chercher « Word » doit ramener un type dont le nom ne contient pas le mot."""
    _ecrire(mimes, "descr.properties",
            "application/vnd.ms-word=Microsoft Word 97-2003\napplication/pdf=PDF\n")
    mc.load()
    noms = [n for n, _e, _l in mc.search("word")]
    assert noms == ["application/vnd.ms-word"]
    assert [n for n, _e, _l in mc.search("pdf")] == ["application/pdf"]


def test_search_couvre_les_noms_observes(mimes):
    mc.learn(["a/observe"])
    assert [n for n, _e, _l in mc.search("observe")] == ["a/observe"]


def test_search_vide_rend_tout_dans_la_limite(mimes):
    mc.learn([f"a/{i}" for i in range(10)])
    assert len(mc.search("")) == 10
    assert len(mc.search("", limit=3)) == 3


# --- Apprentissage ---------------------------------------------------------

def test_learn_ne_rend_que_les_nouveaux(mimes):
    assert mc.learn(["a/b", "c/d"]) == ["a/b", "c/d"]
    assert mc.learn(["a/b"]) == []
    assert mc.learn(["e/f"]) == ["e/f"]


def test_learn_persiste_et_survit_au_rechargement(mimes):
    mc.learn(["a/b", ""])
    mc.load()
    assert mc.status("a/b") == mc.STATUS_OBSERVED
    assert mc.status("") == mc.STATUS_OBSERVED   # le type vide s'apprend aussi


def test_learn_ne_leve_pas_si_dossier_impossible(tmp_path, monkeypatch):
    """Un dossier en lecture seule ne doit pas interrompre un inventaire."""
    cible = tmp_path / "fichier_pas_dossier"
    cible.write_text("x", encoding="utf-8")
    monkeypatch.setattr(config, "mime_dir", lambda: str(cible))
    mc.load()
    assert mc.learn(["a/b"]) == ["a/b"]          # appris en mémoire, non écrit


def test_learn_from_sources(mimes):
    sources = [
        {"domain_boundaries": {"mimeTypes": "a/b,c/d"}},
        {"domain_boundaries": {"mimeTypes": "c/d,e/f"}},
        {"domain_boundaries": {}},
        {},
    ]
    assert mc.learn_from_sources(sources) == ["a/b", "c/d", "e/f"]


# --- Apprentissage depuis un export XML ------------------------------------

def _export_xml(dossier, nom, filtres):
    """Fabrique un export `-exportSourceList` minimal (jamais un cas réel)."""
    corps = "".join(
        f"<source><name>s{i}</name><domainBoundaries>"
        f"<includeMode>Exclude selected entries</includeMode>"
        f"<mimeTypes>{f}</mimeTypes></domainBoundaries></source>"
        for i, f in enumerate(filtres))
    return _ecrire(dossier, nom, f"<sources>{corps}</sources>", encodage="utf-8")


def test_learn_from_xml(mimes, tmp_path):
    chemin = _export_xml(tmp_path, "export.xml", ["a/b,c/d", "c/d,e/f"])
    assert mc.learn_from_xml(chemin) == ["a/b", "c/d", "e/f"]
    assert mc.learn_from_xml(chemin) == []      # déjà connus


def test_learn_from_xml_refuse_un_fichier_hors_sujet(mimes, tmp_path):
    chemin = _ecrire(tmp_path, "autre.xml", "<case><name>x</name></case>",
                     encodage="utf-8")
    with pytest.raises(ValueError):
        mc.learn_from_xml(chemin)


def test_learn_from_xml_signale_l_absence_de_filtre(mimes, tmp_path):
    """« 0 nouveau type » sur un export sans filtre serait un faux négatif."""
    chemin = _export_xml(tmp_path, "vide.xml", [""])
    with pytest.raises(ValueError):
        mc.learn_from_xml(chemin)


def test_learn_from_xml_illisible(mimes, tmp_path):
    chemin = _ecrire(tmp_path, "casse.xml", "<sources><source>", encodage="utf-8")
    with pytest.raises(ValueError):
        mc.learn_from_xml(chemin)


# --- Import d'un référentiel ----------------------------------------------

def test_import_CUMULE_sans_rien_perdre(mimes, tmp_path):
    """Contrat RENVERSÉ le 11/09/2026 : un import complète, il ne remplace plus.

    Avant, installer un nouveau ``.properties`` faisait disparaître les libellés
    absents du nouveau fichier — un filtre jusque-là lisible redevenait muet, et
    rien à l'écran ne disait si l'import avait remplacé ou complété. On importe
    pour GAGNER des libellés : le fichier choisi est donc fusionné, ses entrées
    écrasant celles de même clé et laissant les autres en place.
    """
    _ecrire(mimes, "v1.properties", "a/b=Un\nc/d=Deux\n")
    mc.load()
    source = _ecrire(tmp_path, "v2.properties",
                     "a/b=Un modifie\ne/f=Trois\n")
    bilan = mc.import_descriptions(source)
    assert bilan["added"] == ["e/f"]
    assert bilan["updated"] == ["a/b"]
    assert bilan["count"] == 2
    assert os.path.isfile(bilan["path"])
    assert mc.status("e/f") == mc.STATUS_DESCRIBED
    # LE point du renversement : « c/d » n'était pas dans le nouveau fichier et
    # reste pourtant décrit.
    assert mc.label("c/d") == "Deux"
    assert mc.label("a/b") == "Un modifie"


def test_import_ecrit_un_fichier_cumulatif_unique(mimes, tmp_path):
    """Deux imports successifs alimentent UN seul fichier, pas une pile."""
    mc.load()
    mc.import_descriptions(_ecrire(tmp_path, "a.properties", "x/1=Un\n"))
    mc.import_descriptions(_ecrire(tmp_path, "b.properties", "x/2=Deux\n"))
    assert mc.label("x/1") == "Un"      # le premier import survit au second
    assert mc.label("x/2") == "Deux"
    produits = [f for f in os.listdir(str(mimes)) if f.endswith(".properties")]
    assert produits == [mc.CUMUL_FILENAME]


def test_import_refuse_un_fichier_vide(mimes, tmp_path):
    source = _ecrire(tmp_path, "vide.properties", "# rien que des commentaires\n")
    with pytest.raises(ValueError):
        mc.import_descriptions(source)


def test_import_fichier_absent(mimes):
    with pytest.raises(ValueError):
        mc.import_descriptions(os.path.join(str(mimes), "nexiste_pas.properties"))


# --- Référentiel embarqué : socle, surchargeable --------------------------

def test_embarque_sert_de_socle(tmp_path, monkeypatch):
    """Sans dossier `mimetypes\\`, l'exe nomme quand même les types."""
    monkeypatch.setattr(config, "mime_dir", lambda: str(tmp_path / "absent"))
    monkeypatch.setattr(mime_data, "DESCRIPTIONS", {"a/b": "Embarqué"})
    monkeypatch.setattr(mime_data, "OBSERVED", ["a/b", "c/d"])
    mc.load()
    assert mc.label("a/b") == "Embarqué"
    assert mc.status("c/d") == mc.STATUS_OBSERVED


def test_fichier_externe_COMPLETE_les_descriptions_embarquees(tmp_path, monkeypatch):
    """L'externe l'emporte sur l'embarqué, mais ne l'efface pas (11/09/2026).

    Contrepartie assumée : un type retiré par Vound d'une version future reste
    décrit ici. Sans conséquence — un libellé de trop ne fait rien indexer.
    """
    d = tmp_path / "mimetypes"
    d.mkdir()
    monkeypatch.setattr(config, "mime_dir", lambda: str(d))
    monkeypatch.setattr(mime_data, "DESCRIPTIONS",
                        {"a/b": "Embarqué", "vieux/x": "Toujours là"})
    monkeypatch.setattr(mime_data, "OBSERVED", [])
    _ecrire(d, "neuf.properties", "a/b=Externe\nc/d=Nouveau\n")
    mc.load()
    assert mc.label("a/b") == "Externe"           # collision : l'externe gagne
    assert mc.label("vieux/x") == "Toujours là"   # absent du fichier : conservé
    assert mc.label("c/d") == "Nouveau"
    assert mc.origin("c/d") == "external"
    assert mc.origin("vieux/x") == "embedded"


def test_noms_observes_FUSIONNENT_toujours(tmp_path, monkeypatch):
    """Les noms sont des constats : en perdre ferait réapparaître des « inconnus »."""
    d = tmp_path / "mimetypes"
    d.mkdir()
    monkeypatch.setattr(config, "mime_dir", lambda: str(d))
    monkeypatch.setattr(mime_data, "DESCRIPTIONS", {})
    monkeypatch.setattr(mime_data, "OBSERVED", ["embarque/x"])
    _ecrire(d, mc.OBSERVED_FILENAME, "local/y\n", encodage="utf-8")
    mc.load()
    assert mc.status("embarque/x") == mc.STATUS_OBSERVED
    assert mc.status("local/y") == mc.STATUS_OBSERVED


# --- Absence totale de référentiel : cas NORMAL ---------------------------

def test_sans_referentiel_tout_fonctionne(mimes):
    """Un exe sans référentiel embarqué ni fichier ne doit pas être en panne."""
    assert mc.is_loaded() is False
    assert mc.label("a/b") is None
    assert mc.status("a/b") == mc.STATUS_UNKNOWN
    assert mc.stats()["descriptions"] == 0


def test_le_fichier_le_plus_recent_gagne_les_collisions(mimes):
    import time
    _ecrire(mimes, "vieux.properties", "a/b=Ancien\n")
    time.sleep(0.01)
    _ecrire(mimes, "neuf.properties", "a/b=Recent\n")
    os.utime(os.path.join(str(mimes), "neuf.properties"), None)
    mc.load()
    assert mc.label("a/b") == "Recent"


class TestDescriptionsUtilisateur:
    """Décrire soi-même un type que Vound ne nomme pas (v2.9d).

    Le besoin : sur un filtre réel, 121 noms n'ont aucun libellé. Ce sont des
    alias parfaitement valides, mais illisibles — et personne d'autre que
    l'utilisateur ne peut dire ce qu'ils désignent dans SON contexte.
    """

    def test_ecriture_et_relecture(self, mimes):
        mc.load()
        mc.set_user_label("application/x-truc", "Export du logiciel maison")
        mc.load()                      # relance : la description doit survivre
        assert mc.label("application/x-truc") == "Export du logiciel maison"
        assert mc.status("application/x-truc") == mc.STATUS_USER

    def test_un_type_decrit_par_nous_n_est_plus_inconnu(self, mimes):
        """Sinon il resterait en ROUGE à côté du libellé qu'on vient d'écrire."""
        mc.load()
        assert mc.status("a/inedit") == mc.STATUS_UNKNOWN
        mc.set_user_label("a/inedit", "Mon libellé")
        assert mc.status("a/inedit") != mc.STATUS_UNKNOWN

    def test_vound_prime_sur_nous(self, mimes):
        """Une description officielle ÉCRASE la nôtre — c'est le contrat voulu."""
        mc.load()
        mc.set_user_label("a/b", "Ce que j'en pensais")
        _ecrire(mimes, "descr.properties", "a/b=Le vrai libellé\n")
        mc.load()
        assert mc.label("a/b") == "Le vrai libellé"
        assert mc.status("a/b") == mc.STATUS_DESCRIBED
        # …mais la nôtre n'est pas PERDUE : elle reviendrait avec un référentiel
        # plus ancien. L'effacer serait une perte silencieuse.
        assert mc.user_label("a/b") == "Ce que j'en pensais"

    def test_effacer(self, mimes):
        mc.load()
        mc.set_user_label("a/b", "Un texte")
        mc.set_user_label("a/b", "   ")
        assert mc.user_label("a/b") == ""
        assert "a/b" not in mc.user_labels()

    def test_fichier_illisible_ne_leve_pas(self, mimes):
        _ecrire(mimes, mc.USER_FILENAME, "{ ceci n'est pas du JSON")
        mc.load()
        assert mc.user_labels() == {}
