"""Familles d'extensions d'images forensiques — table unique du projet.

Trois modules portaient chacun leur copie de cette connaissance métier, et les
copies avaient divergé (audit du 18/09/2026) :

- ``forensic_scan`` (panneau « Images forensiques ») connaissait 8 familles ;
- ``path_parser.is_non_first_segment`` (avertissement de saisie) en connaissait 4 ;
- ``sizing._image_segments`` (**calcul du volume d'un cas**) n'en connaissait que 3.

Conséquence du trou dans ``sizing`` : une image LEF (``.l01``), SMART (``.s01``)
ou EWF v2 (``.ex01``) acceptée à l'import ne voyait **aucun** de ses motifs
reconnu ; ``image_size`` retombait sur le fichier seul et ne comptait que le
**premier segment**. Le volume d'un cas était donc sous-évalué, et le garde-fou
des 950 Go pouvait laisser passer un cas qui le dépasse.

Ce module est la seule source de vérité. Il ne dépend d'aucun autre module du
projet (pas de cycle d'import possible).

⚠ **Piège EWF** : au-delà de ``.E99``, la numérotation passe aux lettres
(``.EAA``, ``.EAB``…). Les segments d'une même image relèvent donc de DEUX
motifs — d'où une famille = une extension de premier segment + un **tuple** de
motifs, et non un motif unique.
"""

import re

# Extensions acceptées telles quelles : une image = un fichier, pas de segment.
SINGLE = {".dd", ".vhd", ".vhdx", ".vmdk"}

# Familles à segments : extension du PREMIER segment -> motifs de TOUS les
# segments de la famille. L'ordre compte : les motifs d'une famille sont testés
# avant ceux de la suivante (``.e01`` avant ``.ex01``, ``.l01`` avant ``.lx01``),
# ce qui reproduit l'ordre historique de ``forensic_scan``.
FAMILIES = (
    (".e01", (re.compile(r"^\.e\d{2}$", re.I),
              re.compile(r"^\.e[a-z]{2}$", re.I))),   # EWF : .E01 .E02 … puis .EAA
    (".ex01", (re.compile(r"^\.ex\d{2}$", re.I),)),   # EWF v2
    (".l01", (re.compile(r"^\.l\d{2}$", re.I),)),     # LEF (logique)
    (".lx01", (re.compile(r"^\.lx\d{2}$", re.I),)),
    (".s01", (re.compile(r"^\.s\d{2}$", re.I),)),     # SMART
    (".ad1", (re.compile(r"^\.ad\d+$", re.I),)),      # AD1 : .ad1 .ad2 … .ad28
    (".001", (re.compile(r"^\.\d{3}$"),)),            # brut découpé
)


def _famille(ext: str):
    """``(premier, motifs)`` de la famille de ``ext``, ou ``(None, ())``."""
    ext = (ext or "").lower()
    if not ext:
        return None, ()
    for premier, motifs in FAMILIES:
        if any(m.match(ext) for m in motifs):
            return premier, motifs
    return None, ()


def first_segment_ext(ext: str) -> str:
    """Extension du 1er segment de la famille de ``ext`` ; "" si inconnue.

    ``".e02"`` et ``".eaa"`` rendent tous deux ``".e01"`` : c'est l'extension
    qui identifie l'image entière, utilisable comme clé de décompte.
    """
    return _famille(ext)[0] or ""


def segment_patterns(ext: str) -> tuple:
    """Motifs de TOUS les segments de la famille de ``ext`` ; ``()`` si inconnue.

    Destiné à la collecte des segments d'une image sur disque : un fichier du
    même radical dont l'extension matche l'un de ces motifs appartient à la
    même image.
    """
    return _famille(ext)[1]


def is_segment_ext(ext: str) -> bool:
    """Vrai si ``ext`` appartient à une famille à segments connue."""
    return bool(first_segment_ext(ext))


def is_non_first_segment_ext(ext: str) -> bool:
    """Vrai si ``ext`` est un segment d'une famille connue, mais pas le premier."""
    premier = first_segment_ext(ext)
    return bool(premier) and (ext or "").lower() != premier
