r"""Référentiel des types MIME d'Intella : **décrire** ce qu'un filtre contient.

Un filtre de source (``domainBoundaries/mimeTypes`` dans l'export XML,
``sourceTypeFilter`` en JSON) est une liste de noms techniques —
``application/vnd.ms-word``, ``category/gmail``… — parfaitement illisible dès
qu'elle dépasse quelques entrées, et les filtres réels en comptent **600**.

Deux sources de noms, et il en faut **deux** :

1. **Les descriptions**, fichier ``mimetype-descriptions_<langue>.properties``
   livré avec Intella (679 entrées). Il donne le libellé lisible.
   ⚠ **Rien n'est livré avec IntellaFeeder** : ce fichier appartient à Vound et
   s'importe depuis l'installation d'Intella (onglet Maintenance). Il change
   d'une version d'Intella à l'autre — c'est justement pourquoi il est externe.
2. **Les noms observés**, appris des exports XML que l'application lit déjà.
   Nécessaires parce que **le référentiel ne décrit pas tout** : sur un filtre
   quasi exhaustif (677 noms, constaté le 09/09/2026), **121 sont absents des
   descriptions**. Ce sont des **alias** — ``application/msword``,
   ``application/winword``, ``application/word``, ``application/doc`` pour le
   seul Word, quand le référentiel ne décrit que ``application/vnd.ms-word``.
   Intella écrit dans le XML l'expansion en synonymes de ce qui a été coché.

D'où **trois** états, jamais deux (`status`) :

- ``décrit``   — présent dans les descriptions : on sait le nommer ;
- ``observé``  — déjà vu dans un filtre Intella, sans libellé : **valide**,
  simplement non décrit ;
- ``inconnu``  — jamais vu : à vérifier (faute de frappe, ou version d'Intella
  plus récente que le référentiel importé).

Traiter « absent des descriptions » comme une erreur ferait **121 alertes
rouges** sur un seul filtre réel, et apprendrait à ne plus les regarder.

Module sans interface et sans i18n : ``STATUS_*`` sont des identifiants, c'est
l'UI qui les traduit (même contrat que ``forensic_scan.REASON_*``).
"""

import os
import re

import config

# --- États d'un nom de type ------------------------------------------------
STATUS_DESCRIBED = "described"
STATUS_OBSERVED = "observed"
STATUS_UNKNOWN = "unknown"

# Le référentiel porte une entrée à **clé vide** (`=Untyped`) : c'est un type
# filtrable à part entière, celui des items dont le type n'a pas été déterminé.
# Le `,,` des exports Intella n'est donc pas une scorie.
UNTYPED = ""

DESCRIPTIONS_GLOB = ".properties"
OBSERVED_FILENAME = "noms_observes.txt"

_RE_UNICODE = re.compile(r"\\u([0-9a-fA-F]{4})")

# État chargé (vide tant que `load()` n'a pas tourné).
_descriptions: dict[str, str] = {}
_observed: set[str] = set()
_source_file: str = ""
_duplicates: list[str] = []


# --- Lecture du format .properties ----------------------------------------

def _unescape(text: str) -> str:
    """Déséchappe un `.properties` Java : ``\\uXXXX`` et ``\\:``/``\\=``/``\\ ``."""
    text = _RE_UNICODE.sub(lambda m: chr(int(m.group(1), 16)), text)
    return re.sub(r"\\([:=\s\\])", r"\1", text)


def parse_properties(text: str) -> tuple[dict[str, str], list[str]]:
    """``texte`` → ``({clé: libellé}, [clés en double])``.

    Tolère ce qu'un `.properties` Java autorise et qu'on a constaté ou qui peut
    arriver dans une version future : commentaires ``#``/``!``, lignes de
    continuation, séparateur ``=`` ou ``:``, échappements ``\\uXXXX``.
    **La clé vide est conservée** (``=Untyped``).

    Les doublons sont **résolus comme Java** (la dernière valeur gagne) mais
    **rendus à l'appelant** : le fichier livré par Vound en contient deux, et un
    import silencieux masquerait une anomalie du fichier importé.
    """
    out: dict[str, str] = {}
    doublons: list[str] = []
    tampon = ""
    for brut in text.splitlines():
        ligne = tampon + brut.rstrip("\r")
        tampon = ""
        nu = ligne.lstrip()
        if not nu or nu.startswith("#") or nu.startswith("!"):
            continue
        # Continuation : un antislash final impair prolonge la ligne suivante.
        if (len(ligne) - len(ligne.rstrip("\\"))) % 2 == 1:
            tampon = ligne[:-1]
            continue
        sep = _first_separator(ligne)
        if sep < 0:
            continue
        cle = _unescape(ligne[:sep].strip())
        val = _unescape(ligne[sep + 1:].strip())
        if cle in out:
            doublons.append(cle)
        out[cle] = val
    return out, doublons


def _first_separator(ligne: str) -> int:
    """Position du premier ``=`` ou ``:`` non échappé, ou -1."""
    echappe = False
    for i, ch in enumerate(ligne):
        if echappe:
            echappe = False
            continue
        if ch == "\\":
            echappe = True
        elif ch in "=:":
            return i
    return -1


# --- Emplacement des fichiers ---------------------------------------------

def descriptions_path() -> str:
    """Fichier de descriptions à utiliser : le **plus récent** de ``mimetypes\\``.

    Les imports sont horodatés et l'ancien est conservé (voir
    ``import_descriptions``) : c'est la date de modification qui désigne l'actif,
    pour qu'un retour en arrière soit une simple manipulation de fichiers.
    """
    dossier = config.mime_dir()
    try:
        fichiers = [f for f in os.listdir(dossier)
                    if f.lower().endswith(DESCRIPTIONS_GLOB)]
    except OSError:
        return ""
    if not fichiers:
        return ""
    fichiers.sort(key=lambda f: os.path.getmtime(os.path.join(dossier, f)),
                  reverse=True)
    return os.path.join(dossier, fichiers[0])


def observed_path() -> str:
    """Fichier des noms observés (appris des exports XML lus)."""
    return os.path.join(config.mime_dir(), OBSERVED_FILENAME)


# --- Chargement ------------------------------------------------------------

def load() -> None:
    """(Re)charge descriptions et noms observés. Ne lève jamais.

    Un référentiel absent est un cas **normal** (rien n'est livré avec l'appli) :
    tout continue de fonctionner, sans libellés.
    """
    global _descriptions, _observed, _source_file, _duplicates
    _descriptions, _observed, _duplicates = {}, set(), []
    _source_file = descriptions_path()
    if _source_file:
        try:
            with open(_source_file, encoding="latin-1") as fh:
                _descriptions, _duplicates = parse_properties(fh.read())
        except OSError:
            _descriptions, _duplicates, _source_file = {}, [], ""
    try:
        with open(observed_path(), encoding="utf-8") as fh:
            # Une ligne vide n'est pas une scorie : c'est le seul encodage
            # possible du type « Untyped », dont le nom EST la chaîne vide.
            _observed = {ligne.strip() for ligne in fh}
    except OSError:
        pass


def is_loaded() -> bool:
    """Vrai si au moins une des deux sources a été chargée."""
    return bool(_descriptions or _observed)


def stats() -> dict:
    """Compteurs pour l'écran de maintenance."""
    return {
        "descriptions": len(_descriptions),
        "categories": sum(1 for k in _descriptions if k.startswith("category/")),
        "observed": len(_observed),
        "observed_only": len(_observed - set(_descriptions)),
        "duplicates": len(_duplicates),
        "source": _source_file,
    }


# --- Interrogation ---------------------------------------------------------

def label(nom: str) -> str | None:
    """Libellé lisible d'un type, ou ``None`` s'il n'est pas décrit."""
    return _descriptions.get((nom or "").strip())


def status(nom: str) -> str:
    """``described`` / ``observed`` / ``unknown`` — voir l'en-tête du module."""
    cle = (nom or "").strip()
    if cle in _descriptions:
        return STATUS_DESCRIBED
    if cle in _observed:
        return STATUS_OBSERVED
    return STATUS_UNKNOWN


def describe(nom: str) -> str:
    """Libellé si connu, sinon le nom lui-même — jamais une chaîne vide.

    La clé vide (« Untyped ») rendrait une ligne d'affichage invisible : on lui
    laisse son libellé de référentiel, ou à défaut un texte explicite.
    """
    cle = (nom or "").strip()
    lib = _descriptions.get(cle)
    if lib:
        return lib
    return cle if cle else "(sans type)"


def split_filter(texte: str) -> list[str]:
    """Découpe un filtre (``a,b,,c``) en noms, **clé vide conservée** une fois.

    L'ordre d'apparition est gardé (un filtre relu doit rester comparable à
    celui qui a été émis), les doublons sont écartés.
    """
    vus: list[str] = []
    seen: set[str] = set()
    for part in (texte or "").split(","):
        nom = part.strip()
        if nom in seen:
            continue
        seen.add(nom)
        vus.append(nom)
    return vus


def classify_filter(texte: str) -> list[tuple[str, str, str]]:
    """``[(nom, état, libellé)]`` pour chaque entrée d'un filtre."""
    return [(nom, status(nom), describe(nom)) for nom in split_filter(texte)]


def search(motif: str, limit: int = 500) -> list[tuple[str, str, str]]:
    """Cherche dans **les deux** sources : ``[(nom, état, libellé)]``.

    Le motif est cherché dans le nom **et** dans la description (chercher
    « Word » doit ramener ``application/vnd.ms-word``, dont le nom ne contient
    pas le mot). Motif vide = tout, dans la limite demandée — un référentiel
    complet fait 679 lignes, inutile d'en peindre 10 000.
    """
    m = (motif or "").strip().lower()
    noms = sorted(set(_descriptions) | _observed)
    out: list[tuple[str, str, str]] = []
    for nom in noms:
        if len(out) >= limit:
            break
        if m and m not in nom.lower() and m not in (_descriptions.get(nom, "")).lower():
            continue
        out.append((nom, status(nom), describe(nom)))
    return out


def summarize_filter(texte: str) -> dict:
    """Compte par état — de quoi écrire « 600 types, dont 121 non décrits »."""
    resume = {STATUS_DESCRIBED: 0, STATUS_OBSERVED: 0, STATUS_UNKNOWN: 0}
    noms = split_filter(texte)
    for nom in noms:
        resume[status(nom)] += 1
    resume["total"] = len(noms)
    return resume


# --- Apprentissage ---------------------------------------------------------

def learn(noms) -> list[str]:
    """Enregistre des noms vus dans un export Intella. Retourne les nouveaux.

    Un nom écrit par Intella dans un filtre **est** valide, décrit ou non :
    l'apprentissage évite de signaler comme douteux un alias parfaitement
    légitime. N'écrit que s'il y a du nouveau, et ne lève jamais (un dossier en
    lecture seule ne doit pas interrompre un inventaire).
    """
    nouveaux = sorted({(n or "").strip() for n in noms} - _observed)
    if not nouveaux:
        return []
    _observed.update(nouveaux)
    try:
        os.makedirs(config.mime_dir(), exist_ok=True)
        with open(observed_path(), "w", encoding="utf-8") as fh:
            for nom in sorted(_observed):
                fh.write(nom + "\n")
    except OSError:
        pass
    return nouveaux


def learn_from_xml(chemin: str) -> list[str]:
    """Apprend les types d'un export ``-exportSourceList``. Retourne les nouveaux.

    C'est le **seul moyen de mettre la liste à jour sans outil tiers** : dans
    Intella, créer une source en cochant tout ce que l'interface propose,
    exporter la liste des sources, importer le XML ici. Les noms ainsi récoltés
    sont ceux qu'Intella écrit réellement — alias compris, que le fichier de
    descriptions ne connaît pas.

    Lève ``ValueError`` si le fichier n'est pas un export exploitable : mieux
    vaut le dire que d'annoncer « 0 nouveau type » sur un fichier hors sujet.
    """
    import xml.etree.ElementTree as ET
    try:
        racine = ET.parse(chemin).getroot()
    except (OSError, ET.ParseError) as exc:
        raise ValueError(f"XML illisible : {exc}") from exc
    sources = racine.findall("source")
    if not sources:
        raise ValueError("Ce fichier ne contient aucune <source> "
                         "(attendu : un export -exportSourceList).")
    noms: set[str] = set()
    for src in sources:
        db = src.find("domainBoundaries")
        brut = (db.findtext("mimeTypes") or "").strip() if db is not None else ""
        if brut:
            noms.update(split_filter(brut))
    if not noms:
        raise ValueError("Aucun filtre de types dans cet export : les sources "
                         "n'en déclarent pas.")
    return learn(noms)


def learn_from_sources(sources) -> list[str]:
    """Apprend les types de tous les filtres d'un inventaire.

    ``sources`` = liste de dicts façon ``case_export`` (clé
    ``domain_boundaries`` → ``mimeTypes``).
    """
    noms: set[str] = set()
    for src in sources or []:
        db = (src or {}).get("domain_boundaries") or {}
        brut = (db.get("mimeTypes") or "").strip()
        # Une source SANS filtre n'apprend rien : `split_filter("")` rendrait
        # la chaîne vide, qui ferait croire au type « Untyped ». Celui-ci ne
        # s'apprend que s'il apparaît dans un filtre réel (le `,,`).
        if brut:
            noms.update(split_filter(brut))
    return learn(noms) if noms else []


# --- Import d'un nouveau référentiel --------------------------------------

def import_descriptions(chemin: str) -> dict:
    """Installe un ``.properties`` d'Intella dans ``mimetypes\\``.

    Rend un **bilan avant/après** — ``added`` / ``removed`` / ``duplicates`` —
    parce qu'un référentiel de remplacement qui *perdrait* des noms rendrait
    « non décrits » des filtres jusque-là lisibles. L'ancien fichier est
    conservé (l'import est horodaté) : revenir en arrière reste possible.

    Lève ``ValueError`` si le fichier est illisible ou ne contient aucune entrée
    — mieux vaut refuser qu'installer un référentiel vide.
    """
    try:
        with open(chemin, encoding="latin-1") as fh:
            contenu = fh.read()
    except OSError as exc:
        raise ValueError(f"Fichier illisible : {exc}") from exc
    nouvelles, doublons = parse_properties(contenu)
    if not nouvelles:
        raise ValueError("Aucune description trouvée dans ce fichier.")

    avant = set(_descriptions)
    apres = set(nouvelles)
    cible = os.path.join(
        config.mime_dir(),
        f"{os.path.splitext(os.path.basename(chemin))[0]}_"
        f"{config.now_compact()}.properties")
    os.makedirs(config.mime_dir(), exist_ok=True)
    with open(cible, "w", encoding="latin-1") as fh:
        fh.write(contenu)
    load()
    return {
        "path": cible,
        "count": len(nouvelles),
        "added": sorted(apres - avant),
        "removed": sorted(avant - apres),
        "duplicates": sorted(set(doublons)),
    }
