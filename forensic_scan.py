"""Reconnaissance des images forensiques et collecte récursive dans un dossier.

Sert le panneau « Images forensiques » de l'onglet Import, qui remplace l'outil
externe utilisé jusqu'ici pour produire les listes de chemins : un dossier lâché
dans ce panneau signifie « ajoute les images forensiques qu'il contient ». Par
défaut on s'arrête à ses fichiers ; la descente dans les sous-dossiers est un
choix explicite (case à cocher de l'onglet Import). Le panneau « Dossiers
standard », lui, prend ce qu'on lui donne sans rien inspecter — la différence de
traitement est voulue.

Deux règles, et une seule raison à chaque fois :

- **Extensions connues seulement.** Un dossier de scellés contient aussi des
  rapports, des photos, des exports : les ajouter comme sources produirait un
  import faux, découvert trop tard (Intella ne permet pas de revoir les réglages
  d'une source après import).
- **Premier tronçon uniquement.** IntellaCmd prend l'image entière à partir de
  son premier segment ; lui donner ``.E02`` ou ``.ad2`` casse l'import. Un
  dossier de 40 segments ne doit donc produire qu'UNE ligne.

``.001`` est retenu comme premier segment d'une image brute découpée. En
contexte forensique c'est presque toujours ce que c'est ; le décompte par type
rendu à l'appelant permet de le voir immédiatement, et la croix ✕ du tableau
d'en retirer une ligne posée à tort.
"""

import os
import re

# Extensions acceptées telles quelles (pas de notion de segment).
_SINGLE = {".dd", ".vhd", ".vhdx", ".vmdk"}

# Familles à segments : extension du PREMIER segment -> motif des suivants.
# La valeur est le motif complet de l'extension de la famille ; seul le premier
# segment est retenu, les autres sont refusés avec leur raison.
_FAMILIES = (
    (re.compile(r"^\.e\d{2}$", re.I), ".e01"),        # EWF : .E01 .E02 …
    (re.compile(r"^\.e[a-z]{2}$", re.I), ".e01"),     # EWF au-delà de .E99
    (re.compile(r"^\.ex\d{2}$", re.I), ".ex01"),      # EWF v2
    (re.compile(r"^\.l\d{2}$", re.I), ".l01"),        # LEF (logique)
    (re.compile(r"^\.lx\d{2}$", re.I), ".lx01"),
    (re.compile(r"^\.s\d{2}$", re.I), ".s01"),        # SMART
    (re.compile(r"^\.ad\d+$", re.I), ".ad1"),         # AD1 : .ad1 .ad2 …
    (re.compile(r"^\.\d{3}$", re.I), ".001"),         # brut découpé
)

# Fichiers annexes d'un VMDK : ce ne sont pas des disques à ouvrir seuls.
_VMDK_ANNEXE = re.compile(r"(-s\d+|-flat|-delta|-ctk|-rdm|-rdmp)\.vmdk$", re.I)

# Motifs de refus lisibles par l'utilisateur (l'UI les affiche telles quelles).
REASON_UNKNOWN = "extension non reconnue comme image forensique"
REASON_SEGMENT = "segment non initial — indiquez seulement le 1er"
REASON_VMDK_PART = "fichier annexe VMDK (pas un disque à ouvrir seul)"


def image_kind(path: str) -> str:
    """Type d'image d'un chemin de FICHIER, ou "" s'il n'en est pas un.

    Retourne l'extension normalisée du premier segment (``.e01``, ``.ad1``…),
    utilisable comme clé de décompte pour le compte rendu d'ajout.
    """
    name = os.path.basename(path)
    ext = os.path.splitext(name)[1].lower()
    if not ext:
        return ""
    if ext == ".vmdk":
        return "" if _VMDK_ANNEXE.search(name) else ".vmdk"
    if ext in _SINGLE:
        return ext
    for motif, premier in _FAMILIES:
        if motif.match(ext):
            return premier if ext == premier else ""
    return ""


def refusal_reason(path: str) -> str:
    """Pourquoi ce fichier n'est pas retenu. "" s'il l'est."""
    name = os.path.basename(path)
    ext = os.path.splitext(name)[1].lower()
    if image_kind(path):
        return ""
    if ext == ".vmdk":
        return REASON_VMDK_PART
    for motif, _premier in _FAMILIES:
        if motif.match(ext):
            return REASON_SEGMENT
    return REASON_UNKNOWN


def scan_folder(root: str, on_progress=None, should_stop=None,
                recursive: bool = False) -> tuple[list, dict]:
    """Parcourt ``root`` et retourne ``(chemins, décompte)``.

    ``recursive=False`` par défaut (choix de l'utilisateur, 07/09/2026) : on
    s'arrête aux fichiers du dossier désigné. Un dossier de scellés contient
    souvent d'autres cas, des exports ou des copies de travail — descendre
    d'office ramènerait des images qui n'ont rien à faire dans l'import, et
    l'erreur ne se verrait qu'après l'indexation.

    ``décompte`` : ``{extension: nombre}`` des images retenues, pour un compte
    rendu qui dit ce qui a été ajouté sans faire lire 300 lignes.

    ``on_progress(dossiers_vus, images_trouvées, dossier_courant)`` est appelé
    au fil du parcours (l'appelant cadence l'affichage lui-même), et
    ``should_stop()`` interrompt : un dossier de scellés sur partage réseau se
    parcourt en minutes, et une interruption doit rendre ce qui a été trouvé —
    pas repartir de rien.

    Les dossiers illisibles (droits, partage démonté) sont ignorés en silence :
    ``os.walk`` les saute déjà, et un import bloqué par un sous-dossier
    inaccessible serait pire que la liste partielle.
    """
    found: list[str] = []
    counts: dict[str, int] = {}
    seen = 0
    for dirpath, dirnames, filenames in os.walk(root):
        if should_stop and should_stop():
            break
        seen += 1
        # Vider `dirnames` empêche `os.walk` de descendre (documenté), sans
        # dupliquer la boucle de collecte pour le mode non récursif.
        dirnames[:] = sorted(dirnames) if recursive else []
        for fname in sorted(filenames):
            kind = image_kind(fname)
            if not kind:
                continue
            found.append(os.path.join(dirpath, fname))
            counts[kind] = counts.get(kind, 0) + 1
        if on_progress:
            on_progress(seen, len(found), dirpath)
    return found, counts


def count_subdirs(root: str) -> int:
    """Nombre de sous-dossiers immédiats — 0 si illisible.

    Sert à distinguer « ce dossier ne contient aucune image » de « les images
    sont un cran plus bas » : sans cette nuance, une exploration non récursive
    qui ne ramène rien ressemble à une panne.
    """
    try:
        with os.scandir(root) as it:
            return sum(1 for e in it if e.is_dir())
    except OSError:
        return 0


def classify_paths(paths) -> tuple[list, list, list]:
    """Trie des chemins lâchés sur le panneau « Images forensiques ».

    Retourne ``(dossiers, images, refusés)`` où ``refusés`` est une liste de
    ``(chemin, raison)``. Les dossiers ne sont PAS parcourus ici : le parcours
    peut être long, il appartient à l'appelant de le lancer dans un worker.
    """
    dossiers, images, refuses = [], [], []
    for p in paths:
        # Pas de rstrip des séparateurs ici : « C:\ » y perdrait sa racine.
        # `os.path.isdir` accepte les deux écritures.
        if os.path.isdir(p):
            dossiers.append(p)
        elif image_kind(p):
            images.append(p)
        else:
            refuses.append((p, refusal_reason(p)))
    return dossiers, images, refuses


def summarize_counts(counts: dict) -> str:
    """« 12 × .ad1, 3 × .e01 » — ordre décroissant, pour le journal et l'UI."""
    if not counts:
        return ""
    items = sorted(counts.items(), key=lambda kv: (-kv[1], kv[0]))
    return ", ".join(f"{n} × {ext}" for ext, n in items)
