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


def unc_parts(path: str) -> tuple[str, str, str] | None:
    r"""Découpe un chemin UNC ``\\hôte\partage\reste`` en ``(hôte, partage, reste)``.

    Retourne ``None`` si ce n'est pas un UNC exploitable (lettre de lecteur,
    chemin relatif, préfixe ``\\?\``).
    """
    p = (path or "").replace("/", "\\")
    if not p.startswith("\\\\") or p.startswith("\\\\?\\"):
        return None
    parts = p[2:].split("\\", 2)
    if len(parts) < 2 or not parts[0] or not parts[1]:
        return None
    return parts[0], parts[1], parts[2] if len(parts) > 2 else ""


def align_unc_host(path: str, reference: str) -> str:
    r"""Réécrit l'hôte UNC de ``path`` sur celui de ``reference``, même partage.

    Windows ouvre **une session SMB par nom de serveur** : ``\\NAS\part`` et
    ``\\192.168.0.1\part`` sont deux serveurs distincts, avec des identifiants —
    donc des droits — potentiellement différents. Un cas compound ouvert par le
    nom d'hôte peut déclarer ses sous-cas par IP : joignables en **lecture**, mais
    refusés en **écriture**, ce qui fait échouer ``-exportSourceList`` sur le
    verrou ``case.xml.lock`` (constaté le 07/09/2026).

    Retourne ``path`` inchangé si l'un des deux n'est pas UNC, si le partage
    diffère, ou si l'hôte est déjà celui de la référence (casse ignorée).
    """
    a, b = unc_parts(path), unc_parts(reference)
    if not a or not b:
        return path
    if a[1].lower() != b[1].lower() or a[0].lower() == b[0].lower():
        return path
    tail = "\\" + a[2] if a[2] else ""
    return "\\\\" + b[0] + "\\" + a[1] + tail


def share_key(path: str) -> str:
    r"""Clé de comparaison d'un chemin, **insensible au nom d'hôte** pour un UNC.

    Un même partage se désigne par son nom NetBIOS ou par son IP, et Intella
    enregistre le chemin tel qu'il a été donné : dans un même cas, une source
    peut être en ``\\NAS\part\x`` et une autre en ``\\10.0.0.1\part\y``
    (constaté le 08/09/2026). Comparer les chemins bruts fait alors passer une
    source déjà indexée pour nouvelle — et elle repart à l'import en double.

    On ramène donc l'hôte à ``*``. Le risque assumé est le faux positif : deux
    serveurs différents portant le même nom de partage ET le même sous-chemin.
    L'appelant journalise la correspondance pour qu'elle reste vérifiable.
    """
    parts = unc_parts(path)
    if not parts:
        return normalize_path(path).lower()
    _hote, partage, reste = parts
    tail = "\\" + reste if reste else ""
    return normalize_path("\\\\*\\" + partage + tail).lower()


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
