"""Inventaire des sources d'un cas existant via IntellaCmd.

Utilise ``-exportSourceList <fichier.xml>`` (manuel §25). Le schéma XML a été
constaté sur des exports réels ; le parseur est désormais **ciblé** (et non plus
générique). Structure observée par ``<source>`` :

- ``id``, ``name``, ``type`` (``Disk Image`` / ``File or Folder``), ``timeZone``
- ``size`` : taille en **octets** de l'évidence. Renseignée pour les images
  disque (= ``totalSize``, somme des segments) et les sources « fichier ».
  **Vaut 0 pour les sources « dossier »** → volume inconnu (à confirmer).
- images : ``diskImagePath``, ``partsCount``, ``firstPartName``, ``totalSize`` et
  un ``<path>`` par segment ; sources fichier/dossier : un seul ``<path>``.
- ``tasks`` : tableau JSON des tâches appliquées (id + name).

L'export sert à deux choses : connaître la volumétrie déjà présente (garde-fou
950 Go) et éviter de réindexer une source déjà dans le cas (dédoublonnage par
chemin).
"""

import csv
import os
import shlex
import subprocess
import tempfile
import xml.etree.ElementTree as ET
import json

import config
import path_parser

# Colonnes du CSV (export complet, « Octets » inclus), dans l'ordre d'affichage.
CSV_COLUMNS = [
    "Nom", "Type", "Fuseau", "Taille", "Octets", "Segments", "Chemin", "Tâches",
]
# Colonnes du tableau d'inventaire : « Octets » est volontairement omis de
# l'affichage (redondant avec « Taille ») mais reste présent dans les `rows`
# pour le CSV. Conserve l'ordre du CSV en filtrant « Octets ».
DISPLAY_COLUMNS = [c for c in CSV_COLUMNS if c != "Octets"]

_TYPE_MAP = {
    "Disk Image": config.SOURCE_TYPE_DISK_IMAGE,
    "File or Folder": config.SOURCE_TYPE_FOLDER,
}
_TYPE_LABEL = {
    config.SOURCE_TYPE_DISK_IMAGE: "Image",
    config.SOURCE_TYPE_FOLDER: "Dossier/Fichier",
}


def _split_args(extra: str) -> list[str]:
    """Découpe une chaîne d'arguments en respectant les guillemets (style Windows)."""
    extra = (extra or "").strip()
    if not extra:
        return []
    try:
        return shlex.split(extra, posix=False)
    except ValueError:
        return extra.split()


def run_export_source_list(exe: str, user: str, case_loc: str, log,
                           extra_args: str = "", timeout_min: int = 30):
    """Lance IntellaCmd -exportSourceList et retourne ``(rows, columns, inventory)``.

    ``extra_args`` : arguments supplémentaires (typiquement
    ``-autoSelectFullProcessingLicense``, sans lequel IntellaCmd réclame une
    licence et n'écrit aucun fichier). Lève ``RuntimeError`` en cas d'échec,
    ``FileNotFoundError`` si l'exe est introuvable.
    """
    if not os.path.isfile(exe):
        raise FileNotFoundError(f"IntellaCmd.exe introuvable : {exe}")

    # Dossier temporaire neuf : on NE pré-crée PAS le fichier (mkstemp laissait un
    # fichier de 0 octet qui faussait la détection « non créé »). IntellaCmd écrit
    # sources.xml lui-même dans ce dossier que nous contrôlons.
    tmpdir = tempfile.mkdtemp(prefix="intellafeeder_export_")
    xml_path = os.path.join(tmpdir, "sources.xml")

    cmd = [exe, "-u", user, "-c", case_loc, "-exportSourceList", xml_path,
           "-log", "DEBUG"]
    cmd += _split_args(extra_args)

    log("Exécution : " + subprocess.list2cmdline(cmd))
    try:
        proc = subprocess.run(
            cmd, capture_output=True, text=True,
            encoding="utf-8", errors="replace", timeout=timeout_min * 60,
        )
    except subprocess.TimeoutExpired:
        raise RuntimeError(f"Délai dépassé ({timeout_min} min).")

    if proc.stdout:
        log("stdout IntellaCmd :\n" + proc.stdout.strip())
    if proc.stderr:
        log("stderr IntellaCmd :\n" + proc.stderr.strip())
    log(f"Code retour IntellaCmd : {proc.returncode}")

    if proc.returncode != 0:
        raise RuntimeError(
            f"IntellaCmd a renvoyé le code {proc.returncode}. Voir le journal."
        )
    if not os.path.isfile(xml_path) or os.path.getsize(xml_path) == 0:
        raise RuntimeError(
            "Aucun fichier XML produit par IntellaCmd. Vérifiez la licence "
            "(argument -autoSelectFullProcessingLicense) et le journal."
        )

    parsed = parse_source_list_xml(xml_path)
    rows, columns = to_display_rows(parsed)
    inventory = build_inventory(parsed)
    # Chemin du XML produit (réutilisable : « Info Profil », ré-ouverture).
    inventory["xml_path"] = xml_path
    log(f"{len(parsed['sources'])} source(s) lue(s) dans le cas "
        f"« {parsed['case'].get('name', '?')} ». XML : {xml_path}")
    return rows, columns, inventory


# --------------------------------------------------------------------------- #
# Parsing ciblé                                                               #
# --------------------------------------------------------------------------- #
def _text(elem, tag, default=""):
    child = elem.find(tag)
    if child is not None and child.text:
        return child.text.strip()
    return default


def _int(elem, tag, default=0):
    try:
        return int(_text(elem, tag, str(default)))
    except (ValueError, TypeError):
        return default


def _index_options(elem) -> dict:
    """Bloc ``<indexOptions>`` → dict {tag: texte}. {} si absent."""
    node = elem.find("indexOptions")
    if node is None:
        return {}
    out = {}
    for child in node:
        out[child.tag] = (child.text or "").strip()
    return out


def _domain_boundaries(elem) -> dict:
    """Bloc ``<domainBoundaries>`` → dict (includeMode, mimeTypes,
    fileNameFilters, fileNameFilterAll). {} si absent."""
    node = elem.find("domainBoundaries")
    if node is None:
        return {}
    out = {}
    for child in node:
        out[child.tag] = (child.text or "").strip()
    return out


def _task_objs(elem) -> list:
    """Définitions de tâches (objets JSON) du bloc ``<tasks>`` — format ``tasks.json``."""
    raw = _text(elem, "tasks")
    if not raw:
        return []
    try:
        data = json.loads(raw)
    except (ValueError, TypeError):
        return []
    return [t for t in data if isinstance(t, dict)] if isinstance(data, list) else []


def _task_names(elem) -> list[str]:
    """Noms des tâches (depuis les objets ``<tasks>``)."""
    names = []
    for t in _task_objs(elem):
        name = (t.get("name") or t.get("id") or "").strip()
        if name:
            names.append(name)
    return names


# Champs NON identifiants d'une tâche : `id` (UUID propre par source) et `name`
# (éditable par l'utilisateur). La signature = définition fonctionnelle restante.
_TASK_NON_ID_KEYS = ("id", "name")


def _canonical(value):
    """Forme canonique **ordre-insensible** : chaque liste devient un multiset
    (éléments triés par contenu sérialisé). Deux tâches dont seul l'ordre des
    actions/conditions diffère (« fonctions inversées ») ont alors la même forme."""
    if isinstance(value, dict):
        return {k: _canonical(v) for k, v in value.items()}
    if isinstance(value, list):
        return sorted((_canonical(v) for v in value),
                      key=lambda x: json.dumps(x, sort_keys=True, ensure_ascii=False))
    return value


def _task_signature(obj: dict) -> str:
    """Signature fonctionnelle d'une tâche : **hors `id`/`name`** et
    **insensible à l'ordre** des listes (actions/conditions). Déduplique donc les
    tâches identiques au nom/UUID près ET celles aux fonctions simplement inversées.

    ⚠ La tâche conservée est la **1ʳᵉ rencontrée** : c'est SON ordre d'actions qui
    sera réellement appliqué à l'import (les variantes réordonnées sont fusionnées
    dessus). Acceptable si l'ordre est jugé non significatif pour ces tâches."""
    stripped = {k: v for k, v in obj.items() if k not in _TASK_NON_ID_KEYS}
    return json.dumps(_canonical(stripped), sort_keys=True, ensure_ascii=False)


def parse_source_list_xml(xml_path: str) -> dict:
    """Parse le XML en ``{case: {...}, sources: [ {...}, ... ]}``."""
    tree = ET.parse(xml_path)
    root = tree.getroot()

    case = {
        "id": _text(root, "caseId"),
        "name": _text(root, "caseName"),
        "path": _text(root, "casePath"),
    }

    sources = []
    for elem in root.findall("source"):
        type_raw = _text(elem, "type")
        type_norm = _TYPE_MAP.get(type_raw, type_raw)
        size = _int(elem, "size")
        paths = [p.text.strip() for p in elem.findall("path") if p.text and p.text.strip()]
        disk_image_path = _text(elem, "diskImagePath")
        primary = disk_image_path or (paths[0] if paths else "")

        is_image = type_norm == config.SOURCE_TYPE_DISK_IMAGE
        total_size = _int(elem, "totalSize") if is_image else None
        # Volume effectif de l'évidence : pour une image multi-segments, ``size``
        # ne donne que le 1ᵉ segment → c'est ``totalSize`` (somme des segments)
        # qu'il faut compter. Pour fichier/dossier, ``size`` (0 si dossier).
        eff_bytes = total_size if is_image else size
        sources.append({
            "name": _text(elem, "name"),
            "type_raw": type_raw,
            "type": type_norm,
            "timezone": _text(elem, "timeZone"),
            "size": size,
            "total_size": total_size,
            "bytes": eff_bytes,
            "parts_count": _int(elem, "partsCount") if is_image else None,
            "primary_path": primary,
            "paths": paths,
            "disk_image_path": disk_image_path,
            "task_names": _task_names(elem),
            "task_objs": _task_objs(elem),
            # Réglages d'indexation (pour « Info Profil » → onglet Profils).
            "index_options": _index_options(elem),
            "domain_boundaries": _domain_boundaries(elem),
            # Volume inconnu = source « dossier/fichier » dont la taille vaut 0
            # (Intella ne reporte pas la taille des dossiers).
            "size_unknown": (not is_image) and size == 0,
        })

    return {"case": case, "sources": sources}


def to_display_rows(parsed: dict):
    """Construit ``(rows, columns)`` lisibles pour le tableau et le CSV."""
    rows = []
    for s in parsed["sources"]:
        if s["size_unknown"]:
            taille = "à mesurer"
        else:
            taille = config.human_size(s["bytes"])
        rows.append({
            "Nom": s["name"],
            "Type": _TYPE_LABEL.get(s["type"], s["type_raw"]),
            "Fuseau": s["timezone"],
            "Taille": taille,
            "Octets": str(s["bytes"]),
            "Segments": str(s["parts_count"]) if s["parts_count"] else "",
            "Chemin": s["primary_path"],
            "Tâches": " | ".join(s["task_names"]),
        })
    return rows, list(DISPLAY_COLUMNS)


# --------------------------------------------------------------------------- #
# Inventaire exploité par l'onglet Import                                      #
# --------------------------------------------------------------------------- #
def _norm(p: str) -> str:
    """Clé de dédoublonnage : chemin normalisé, casse ignorée."""
    return path_parser.normalize_path(p).lower()


def build_inventory(parsed: dict) -> dict:
    """Résumé transmis à l'onglet Import (volume + chemins déjà indexés).

    - ``existing_paths`` : ensemble des chemins déjà indexés (tous segments +
      diskImagePath), normalisés, pour le dédoublonnage.
    - ``known_bytes`` : somme des tailles connues (images + fichiers). **Borne
      basse** : les sources « dossier » (size 0) ne sont pas comptées.
    - ``folder_unknown`` : sources dossier à la taille non reportée.
    """
    existing_paths: set[str] = set()
    known_bytes = 0
    folder_unknown = []

    case_tasks: list = []          # définitions de tâches recyclables (dédupliquées)
    seen_task_sigs: set = set()
    for s in parsed["sources"]:
        for p in s["paths"]:
            existing_paths.add(_norm(p))
        if s["disk_image_path"]:
            existing_paths.add(_norm(s["disk_image_path"]))
        if s["primary_path"]:
            existing_paths.add(_norm(s["primary_path"]))
        if s["size_unknown"]:
            folder_unknown.append({"name": s["name"], "path": s["primary_path"]})
        else:
            known_bytes += s["bytes"]
        # Recyclage des tâches : union dédupliquée par signature (hors UUID).
        for obj in s.get("task_objs", []):
            sig = _task_signature(obj)
            if sig not in seen_task_sigs:
                seen_task_sigs.add(sig)
                case_tasks.append(obj)

    return {
        "case_name": parsed["case"].get("name", ""),
        "case_path": parsed["case"].get("path", ""),
        "case_path_key": _norm(parsed["case"].get("path", "")),
        "existing_paths": existing_paths,
        "known_bytes": known_bytes,
        "folder_unknown": folder_unknown,
        "source_count": len(parsed["sources"]),
        "case_tasks": case_tasks,
        # Sources détaillées (même ordre que les lignes affichées) : réglages
        # d'indexation pour « Info Profil ».
        "sources_detail": parsed["sources"],
    }


def export_csv(rows, columns, path: str) -> None:
    """Écrit l'inventaire en CSV (UTF-8 BOM pour Excel)."""
    with open(path, "w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=columns, extrasaction="ignore")
        writer.writeheader()
        for r in rows:
            writer.writerow({c: r.get(c, "") for c in columns})
