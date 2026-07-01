"""Calcul de la taille des sources et partition en lots (cas compound)."""

import os
import re

import config

_RE_EWF = re.compile(r"\.e\d{2}$", re.IGNORECASE)   # .E01, .E02, ...
_RE_SPLIT_DD = re.compile(r"\.\d{3}$")              # .001, .002, ...
_RE_AD1 = re.compile(r"\.ad\d+$", re.IGNORECASE)    # .ad1, .ad2, ... .ad28


def _safe_size(path: str) -> int:
    try:
        return os.path.getsize(path)
    except OSError:
        return 0


def folder_size(path: str) -> int:
    """Somme récursive des tailles de fichiers d'un dossier."""
    total = 0
    for root, _dirs, files in os.walk(path):
        for name in files:
            total += _safe_size(os.path.join(root, name))
    return total


def image_size(path: str) -> int:
    """Taille d'une image, en sommant TOUS les segments le cas échéant.

    Gère EWF (.E01, .E02, …) et split dd (.001, .002, …) ; sinon taille du
    fichier unique.
    """
    if not os.path.exists(path):
        return 0
    directory = os.path.dirname(path)
    stem, ext = os.path.splitext(os.path.basename(path))

    pattern = None
    if _RE_EWF.fullmatch(ext):
        pattern = _RE_EWF
    elif _RE_SPLIT_DD.fullmatch(ext):
        pattern = _RE_SPLIT_DD
    elif _RE_AD1.fullmatch(ext):
        pattern = _RE_AD1

    if pattern is None:
        return _safe_size(path)

    total = 0
    try:
        entries = os.listdir(directory)
    except OSError:
        return _safe_size(path)
    for name in entries:
        s, e = os.path.splitext(name)
        if s == stem and pattern.fullmatch(e):
            total += _safe_size(os.path.join(directory, name))
    return total


def source_size(source) -> int:
    """Taille (octets) d'une Source selon son type."""
    path = source.path
    if source.source_type == config.SOURCE_TYPE_DISK_IMAGE:
        return image_size(path)
    if os.path.isfile(path):
        return _safe_size(path)
    if os.path.isdir(path):
        return folder_size(path)
    return 0


def oversized_sources(sources, limit_bytes: int):
    """Sources dont la taille seule dépasse la limite (non fractionnables)."""
    return [s for s in sources if (s.size_bytes or 0) > limit_bytes]
