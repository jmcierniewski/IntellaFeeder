"""Analyse des chemins collés dans les panneaux et utilitaires associés."""

import os
import re

from models import Source

# Segments d'image probablement NON initiaux : .E02+, .002+, .s02+ ...
_RE_EWF = re.compile(r"\.E(\d{2})$", re.IGNORECASE)        # .E01, .E02, ...
_RE_DD = re.compile(r"\.(\d{3})$")                          # .001, .002, ...
_RE_SPLIT = re.compile(r"\.s(\d{2})$", re.IGNORECASE)      # .s01, .s02, ...
_RE_AD1 = re.compile(r"\.ad(\d+)$", re.IGNORECASE)        # .ad1, .ad2, ... .ad28


def normalize_path(raw: str) -> str:
    """Nettoie une ligne collée : espaces, guillemets, séparateurs de fin.

    Conserve la racine d'un lecteur (ex. ``C:\\``) intacte.
    """
    p = raw.strip().strip('"').strip("'").strip()
    if len(p) > 3:  # ne pas réduire "C:\" à "C:"
        p = p.rstrip("\\/")
    return p


def clean_field(raw: str) -> str:
    """Nettoie un champ de chemin (guillemets, espaces) — consigne projet.

    Utilisé pour tous les champs de chemin de l'UI (cas, exe, sortie, tâches…).
    """
    return normalize_path(raw)


def derive_name(path: str) -> str:
    """Nom de source par défaut = dernier composant du chemin."""
    base = os.path.basename(path.rstrip("\\/"))
    return base or path


def is_non_first_segment(path: str) -> bool:
    """Vrai si le chemin ressemble à un segment d'image NON initial.

    Sert uniquement à émettre un avertissement (IntellaCmd attend le 1er segment).
    """
    m = _RE_EWF.search(path)
    if m and m.group(1) != "01":
        return True
    m = _RE_DD.search(path)
    if m and m.group(1) != "001":
        return True
    m = _RE_SPLIT.search(path)
    if m and m.group(1) != "01":
        return True
    m = _RE_AD1.search(path)
    if m and int(m.group(1)) != 1:   # 1er segment AD1 = .ad1
        return True
    return False


def parse_lines(text: str, source_type: str) -> list[Source]:
    """Transforme un bloc de texte (une ligne = un chemin) en liste de Source.

    Les lignes vides sont ignorées ; les doublons internes (même chemin,
    casse ignorée) sont supprimés.
    """
    sources: list[Source] = []
    seen: set[str] = set()
    for line in text.splitlines():
        path = normalize_path(line)
        if not path:
            continue
        key = path.lower()
        if key in seen:
            continue
        seen.add(key)
        sources.append(
            Source(name=derive_name(path), path=path, source_type=source_type)
        )
    return sources
