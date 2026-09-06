"""Lecture des métadonnées d'un dossier de cas Intella.

Trois fichiers utiles dans un dossier de cas :
- ``case.xml`` (racine)        : id, name, description, timestamp (création, epoch ms),
                                 lastOpened (epoch ms), user, size (octets), versions.
- ``prefs\\case.prefs``        : lignes ``clé=valeur`` (OptimizationFolderPath,
                                 InitialAuthorizedUsers, Tasks*Done, hachage…).
- ``prefs\\tasks2.json`` (opt) : tâches lancées après indexation / à la consultation.

La présence de ``case.xml`` sert à valider qu'on pointe bien sur un dossier de cas
et à récupérer automatiquement le nom du cas, l'utilisateur et la taille occupée.

**Cas compound** : la racine porte ``compound="true"`` et un bloc ``<subcases>``
listant un ``<subcase>`` par sous-cas (chemin ABSOLU du dossier du sous-cas). Un
compound ne contient aucune source en propre : il référence ses sous-cas, porte
la taille TOTALE de l'ensemble et la liste des utilisateurs autorisés.
``IntellaCmd -addSourcesFromJson`` ne peut donc PAS y ajouter de source (il faut
viser un sous-cas) → l'onglet Import est neutralisé pour ce type de cas.
Les chemins de sous-cas peuvent pointer hors du poste courant (partage réseau
démonté, cas recopié sans ses sous-cas) : ``read_subcases`` le signale au lieu
de lever.
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


def tasks2_path(folder: str) -> str:
    """Chemin de ``prefs\\tasks2.json`` (peut ne pas exister)."""
    return os.path.join(folder, PREFS_DIR, TASKS2_JSON)


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
        # Cas compound : marqueur + chemins des sous-cas référencés.
        "compound": (root.get("compound", "") or "").strip().lower() == "true",
        "subcase_paths": _subcase_paths(root),
    }


def _subcase_paths(root) -> list[str]:
    """Chemins des sous-cas déclarés par ``<subcases><subcase>…``. [] si absent."""
    node = root.find("subcases")
    if node is None:
        return []
    return [el.text.strip() for el in node.findall("subcase")
            if el.text and el.text.strip()]


def authorized_users(prefs: dict) -> list[str]:
    """Utilisateurs autorisés du cas, depuis ``InitialAuthorizedUsers`` (CSV)."""
    raw = prefs.get("InitialAuthorizedUsers", "") or ""
    return [u.strip() for u in raw.split(",") if u.strip()]


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
    path = tasks2_path(folder)
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


def read_subcases(folder: str, paths: list[str] | None = None) -> list[dict]:
    """Détaille les sous-cas d'un cas compound, sans IntellaCmd.

    ``paths`` évite une relecture du ``case.xml`` parent quand l'appelant les a
    déjà (``xml["subcase_paths"]``).

    Chaque entrée : ``path`` (chemin déclaré), ``exists`` (dossier + ``case.xml``
    lisibles), ``name``, ``user``, ``size``, ``authorized_users`` et ``error``
    (motif de l'échec, sinon ""). Ne lève jamais : un sous-cas hors du poste
    (partage démonté, cas recopié seul) reste une ligne d'inventaire signalée,
    pas une erreur bloquante.
    """
    if paths is None:
        try:
            paths = read_case_xml(folder)["subcase_paths"]
        except (ET.ParseError, OSError):
            return []

    out: list[dict] = []
    for raw in paths:
        path = os.path.normpath(raw)
        entry = {
            "path": path,
            "exists": False,
            # Repli d'affichage tant que le case.xml n'est pas lisible : le nom
            # du dossier, presque toujours celui du sous-cas.
            "name": os.path.basename(path.rstrip(r"\\/")) or path,
            "user": "",
            "size": 0,
            "authorized_users": [],
            "error": "",
        }
        if not os.path.isdir(path):
            entry["error"] = i18n.t(
                "case_meta.subcase_missing_dir",
                "Dossier introuvable depuis ce poste.")
        elif not has_case_xml(path):
            entry["error"] = i18n.t(
                "case_meta.subcase_no_case_xml",
                "Dossier présent mais case.xml absent.")
        else:
            try:
                sub = read_case_xml(path)
                prefs = read_prefs(path)
            except (ET.ParseError, OSError) as exc:
                entry["error"] = i18n.t(
                    "case_meta.subcase_unreadable",
                    "case.xml illisible : {e}", e=exc)
            else:
                entry.update({
                    "exists": True,
                    "name": sub["name"] or entry["name"],
                    "user": sub["user"],
                    "size": sub["size"],
                    "authorized_users": authorized_users(prefs),
                })
        out.append(entry)
    return out


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
        "authorized_users": authorized_users(prefs),
        # Cas compound : pas de source en propre, import interdit (cf. docstring).
        "is_compound": xml["compound"],
        "subcases": read_subcases(folder, xml["subcase_paths"]) if xml["compound"] else [],
    }
