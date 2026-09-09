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


@pytest.fixture
def mimes(tmp_path, monkeypatch):
    """Isole ``mimetypes\\`` et repart d'un référentiel vide."""
    d = tmp_path / "mimetypes"
    d.mkdir()
    monkeypatch.setattr(config, "mime_dir", lambda: str(d))
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
                      mc.STATUS_UNKNOWN: 0, "total": 2}


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

def test_import_bilan_ajouts_et_pertes(mimes, tmp_path):
    _ecrire(mimes, "v1.properties", "a/b=Un\nc/d=Deux\n")
    mc.load()
    source = _ecrire(tmp_path, "v2.properties", "a/b=Un\ne/f=Trois\n")
    bilan = mc.import_descriptions(source)
    assert bilan["added"] == ["e/f"]
    assert bilan["removed"] == ["c/d"]           # perte signalée AVANT usage
    assert bilan["count"] == 2
    assert os.path.isfile(bilan["path"])
    assert mc.status("e/f") == mc.STATUS_DESCRIBED


def test_import_conserve_l_ancien_fichier(mimes, tmp_path):
    _ecrire(mimes, "v1.properties", "a/b=Un\n")
    mc.load()
    mc.import_descriptions(_ecrire(tmp_path, "v2.properties", "a/b=Un\n"))
    restants = [f for f in os.listdir(str(mimes)) if f.endswith(".properties")]
    assert len(restants) == 2


def test_import_refuse_un_fichier_vide(mimes, tmp_path):
    source = _ecrire(tmp_path, "vide.properties", "# rien que des commentaires\n")
    with pytest.raises(ValueError):
        mc.import_descriptions(source)


def test_import_fichier_absent(mimes):
    with pytest.raises(ValueError):
        mc.import_descriptions(os.path.join(str(mimes), "nexiste_pas.properties"))


# --- Absence de référentiel : cas NORMAL ----------------------------------

def test_sans_referentiel_tout_fonctionne(mimes):
    """Rien n'est livré avec l'application : l'absence n'est pas une panne."""
    assert mc.is_loaded() is False
    assert mc.label("a/b") is None
    assert mc.status("a/b") == mc.STATUS_UNKNOWN
    assert mc.stats()["descriptions"] == 0


def test_descriptions_path_prend_le_plus_recent(mimes):
    import time
    _ecrire(mimes, "vieux.properties", "a/b=Ancien\n")
    time.sleep(0.01)
    _ecrire(mimes, "neuf.properties", "a/b=Recent\n")
    os.utime(os.path.join(str(mimes), "neuf.properties"), None)
    mc.load()
    assert mc.label("a/b") == "Recent"
