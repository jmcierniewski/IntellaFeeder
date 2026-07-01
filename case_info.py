"""Fichier d'informations propre à un cas : ``IF_<nom du cas>.info``.

Déposé **à la racine du dossier de cas** (à côté de ``case.xml``). Format JSON.
But : mémoriser, d'un inventaire à l'autre, des informations coûteuses à
recalculer ou des préférences propres au cas.

Contenu actuel :
- ``folder_sizes`` : cache générique **chemin → octets**, clé = chemin normalisé
  (minuscule). Alimenté par deux usages : (1) l'onglet Inventaire, « Scanner les
  dossiers à 0 » (sources « dossier » que Intella reporte à 0 — seuls les
  **nouveaux** sont rescannés) ; (2) l'onglet Import, « Calculer la taille »
  (nouvelles sources pas encore importées — une source déjà mesurée lors d'une
  session précédente n'est pas rescannée). Malgré son nom, ne se limite pas aux
  dossiers.
- ``skip_integrity_check`` : booléen — ne pas vérifier l'intégrité des sources à
  l'import (contournement du bug Vound sur les images forensiques multi-tronçons,
  cf. ``validateDiskImage:false``).

Le fichier est créé à la demande (au 1er scan / 1er réglage) s'il n'existe pas.
"""

import json
import os

import config
import path_parser

INFO_PREFIX = "IF_"
INFO_EXT = ".info"


def info_path(folder: str, case_name: str) -> str:
    """Chemin du fichier ``IF_<nom assaini>.info`` à la racine du cas."""
    return os.path.join(folder, INFO_PREFIX + config.sanitize_filename(case_name) + INFO_EXT)


def _default(case_name: str) -> dict:
    return {
        "app": config.APP_NAME,
        "case_name": case_name,
        "updated": "",
        "folder_sizes": {},
        "skip_integrity_check": False,
    }


def read_info(folder: str, case_name: str) -> dict:
    """Lit le fichier .info du cas (dict). Retourne les valeurs par défaut si
    absent ou illisible (jamais d'exception)."""
    data = _default(case_name)
    path = info_path(folder, case_name)
    if not os.path.isfile(path):
        return data
    try:
        with open(path, encoding="utf-8") as f:
            loaded = json.load(f)
        if isinstance(loaded, dict):
            data.update(loaded)
            if not isinstance(data.get("folder_sizes"), dict):
                data["folder_sizes"] = {}
    except (OSError, ValueError):
        pass
    return data


def write_info(folder: str, case_name: str, data: dict) -> bool:
    """Écrit le fichier .info (créé s'il n'existe pas). Retourne True si OK."""
    data = dict(data)
    data["app"] = config.APP_NAME
    data["case_name"] = case_name
    data["updated"] = config.now_str()
    try:
        with open(info_path(folder, case_name), "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        return True
    except OSError:
        return False


# --- Helpers ciblés ------------------------------------------------------- #
def _key(p: str) -> str:
    return path_parser.normalize_path(p).lower()


def get_folder_sizes(folder: str, case_name: str) -> dict:
    """Tailles de dossiers mémorisées, clé = chemin normalisé minuscule."""
    return read_info(folder, case_name).get("folder_sizes", {}) or {}


def update_folder_sizes(folder: str, case_name: str, measured: dict) -> bool:
    """Fusionne ``measured`` (chemin -> octets) dans le cache et réécrit le .info."""
    data = read_info(folder, case_name)
    sizes = data.get("folder_sizes") or {}
    for p, b in measured.items():
        sizes[_key(p)] = int(b)
    data["folder_sizes"] = sizes
    return write_info(folder, case_name, data)


def get_skip_integrity(folder: str, case_name: str) -> bool:
    return bool(read_info(folder, case_name).get("skip_integrity_check", False))


def set_skip_integrity(folder: str, case_name: str, value: bool) -> bool:
    data = read_info(folder, case_name)
    data["skip_integrity_check"] = bool(value)
    return write_info(folder, case_name, data)
