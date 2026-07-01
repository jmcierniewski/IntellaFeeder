"""Lecture des métadonnées d'un dossier de cas Intella.

Trois fichiers utiles dans un dossier de cas :
- ``case.xml`` (racine)        : id, name, description, timestamp (création, epoch ms),
                                 lastOpened (epoch ms), user, size (octets), versions.
- ``prefs\\case.prefs``        : lignes ``clé=valeur`` (OptimizationFolderPath,
                                 InitialAuthorizedUsers, Tasks*Done, hachage…).
- ``prefs\\tasks2.json`` (opt) : tâches lancées après indexation / à la consultation.

La présence de ``case.xml`` sert à valider qu'on pointe bien sur un dossier de cas
et à récupérer automatiquement le nom du cas, l'utilisateur et la taille occupée.
"""

import json
import os
import xml.etree.ElementTree as ET

import i18n

CASE_XML = "case.xml"
PREFS_DIR = "prefs"
CASE_PREFS = "case.prefs"
TASKS2_JSON = "tasks2.json"


def case_xml_path(folder: str) -> str:
    return os.path.join(folder, CASE_XML)


def has_case_xml(folder: str) -> bool:
    return bool(folder) and os.path.isfile(case_xml_path(folder))


def _text(root, tag: str, default: str = "") -> str:
    el = root.find(tag)
    if el is not None and el.text:
        return el.text.strip()
    return default


def read_case_xml(folder: str) -> dict:
    """Parse ``case.xml`` → dict. Lève si fichier absent/illisible."""
    tree = ET.parse(case_xml_path(folder))
    root = tree.getroot()

    def gi(tag: str) -> int:
        try:
            return int(_text(root, tag, "0"))
        except (ValueError, TypeError):
            return 0

    return {
        "id": root.get("id", ""),
        "name": _text(root, "name"),
        "description": _text(root, "description"),
        "timestamp": gi("timestamp"),
        "lastOpened": gi("lastOpened"),
        "user": _text(root, "user"),
        "size": gi("size"),
        "originalVersion": _text(root, "originalVersion"),
        "caseVersion": _text(root, "caseVersion"),
    }


def read_prefs(folder: str) -> dict:
    """Parse ``prefs\\case.prefs`` (lignes clé=valeur). Vide si absent."""
    path = os.path.join(folder, PREFS_DIR, CASE_PREFS)
    prefs: dict[str, str] = {}
    if not os.path.isfile(path):
        return prefs
    try:
        with open(path, encoding="utf-8", errors="replace") as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith("#") or "=" not in line:
                    continue
                key, val = line.split("=", 1)
                prefs[key.strip()] = val.strip()
    except OSError:
        pass
    return prefs


def read_tasks2(folder: str) -> list[str]:
    """Noms des tâches de ``prefs\\tasks2.json`` (post-indexation). [] si absent."""
    path = os.path.join(folder, PREFS_DIR, TASKS2_JSON)
    names: list[str] = []
    if not os.path.isfile(path):
        return names
    try:
        with open(path, encoding="utf-8", errors="replace") as f:
            data = json.load(f)
        for t in data if isinstance(data, list) else []:
            name = (t.get("name") or t.get("id") or "").strip()
            if name:
                names.append(name)
    except (ValueError, OSError, AttributeError):
        pass
    return names


def read_case(folder: str) -> dict:
    """Métadonnées complètes d'un dossier de cas.

    Lève ``FileNotFoundError`` si ``case.xml`` est absent (= pas un dossier de cas
    valide, ou mauvais chemin).
    """
    if not has_case_xml(folder):
        raise FileNotFoundError(i18n.t(
            "case_meta.err_no_case_xml",
            "case.xml introuvable à cet emplacement. Vérifiez que vous pointez "
            "bien sur le dossier d'un cas Intella."
        ))
    xml = read_case_xml(folder)
    prefs = read_prefs(folder)
    return {
        "folder": folder,
        "xml": xml,
        "prefs": prefs,
        "tasks2": read_tasks2(folder),
        # Raccourcis fréquents :
        "name": xml["name"],
        "user": xml["user"],
        "size": xml["size"],
        "optimization": prefs.get("OptimizationFolderPath", ""),
    }
