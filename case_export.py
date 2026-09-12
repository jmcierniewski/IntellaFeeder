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
# Cas compound : les sources proviennent des sous-cas, une colonne dit lequel.
# Placée en tête (c'est la clé de lecture du tableau), aussi bien à l'écran
# qu'au CSV — d'où les listes dérivées plutôt qu'une modification des constantes.
SUBCASE_COLUMN = "Sous-cas"
CSV_COLUMNS_COMPOUND = [SUBCASE_COLUMN] + CSV_COLUMNS
DISPLAY_COLUMNS_COMPOUND = [SUBCASE_COLUMN] + DISPLAY_COLUMNS

_TYPE_MAP = {
    "Disk Image": config.SOURCE_TYPE_DISK_IMAGE,
    "File or Folder": config.SOURCE_TYPE_FOLDER,
}
# Libellé de la colonne « Taille » quand Intella ne reporte rien (source
# « dossier »). Partagé avec l'UI, qui doit distinguer « pas encore mesuré » de
# « mesuré et vraiment vide » — deux choses très différentes à l'import.
SIZE_UNKNOWN_LABEL = "à mesurer"

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


def diagnose_no_xml(stdout: str, stderr: str) -> str:
    """Motif probable d'un ``-exportSourceList`` qui n'écrit aucun XML.

    IntellaCmd **renvoie 0 même en échec** : seul le contenu des flux dit ce qui
    s'est passé. Sans ce tri, tout échec était imputé à la licence — ce qui a
    envoyé chercher au mauvais endroit un refus d'écriture sur un partage
    (07/09/2026, cas compound dont les sous-cas sont déclarés par IP).
    """
    blob = (stdout or "") + "\n" + (stderr or "")
    if "AccessDeniedException" in blob and ".lock" in blob:
        return (
            "Accès refusé au verrou « case.xml.lock » : IntellaCmd doit pouvoir "
            "ÉCRIRE dans le dossier du cas, pas seulement le lire. À vérifier : "
            "droits d'écriture sur le partage (une connexion par ADRESSE IP peut "
            "être plus restreinte que par nom de serveur), attribut « lecture "
            "seule » sur le dossier, ou cas déjà ouvert ailleurs."
        )
    if "AccessDeniedException" in blob or "NoSuchFileException" in blob:
        return ("Accès refusé ou fichier introuvable côté IntellaCmd "
                "(voir la trace Java dans le journal).")
    # « Using license: … » figure aussi dans les exécutions RÉUSSIES : ne conclure
    # à la licence que sur un marqueur d'absence ou de sélection interactive.
    low = blob.lower()
    for marker in ("no license", "no valid license", "select a license",
                   "licenses available: 0", "aucune licence"):
        if marker in low:
            return ("Aucune licence utilisable n'a été sélectionnée (argument "
                    "-autoSelectFullProcessingLicense).")
    return ""


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
        detail = diagnose_no_xml(proc.stdout, proc.stderr)
        raise RuntimeError(
            "Aucun fichier XML produit par IntellaCmd. "
            + (detail or "Vérifiez la licence (argument "
                         "-autoSelectFullProcessingLicense) et le journal.")
        )

    parsed = parse_source_list_xml(xml_path)
    rows, columns = to_display_rows(parsed)
    inventory = build_inventory(parsed)
    # Chemin du XML produit (réutilisable : « Info Profil », ré-ouverture).
    inventory["xml_path"] = xml_path
    log(f"{len(parsed['sources'])} source(s) lue(s) dans le cas "
        f"« {parsed['case'].get('name', '?')} ». XML : {xml_path}")
    return rows, columns, inventory


def run_export_subcases(exe: str, user: str, subcases: list, log,
                        extra_args: str = "", timeout_min: int = 30,
                        case_name: str = "", case_path: str = ""):
    """Inventaire d'un cas COMPOUND : un ``-exportSourceList`` par sous-cas.

    Un compound ne porte aucune source en propre — il référence des sous-cas
    (cf. ``case_meta``). On interroge donc chaque sous-cas accessible, puis on
    concatène les résultats en ajoutant la colonne « Sous-cas ».

    ``subcases`` : sortie de ``case_meta.read_subcases`` (les entrées dont
    ``exists`` est faux sont reportées sans être interrogées).

    **Un sous-cas en échec n'interrompt pas les autres** : chacun a sa ligne dans
    ``inventory["subcase_reports"]`` (``ok`` / ``error``). ``RuntimeError`` n'est
    levée que si AUCUN sous-cas n'a pu être lu — sinon l'inventaire partiel est
    plus utile que rien, à condition que l'appelant affiche les échecs.

    Retourne ``(rows, columns, inventory)``, comme ``run_export_source_list``.
    """
    rows: list = []
    reports: list = []
    xml_paths: list = []
    existing_paths: set = set()
    existing_share_keys: set = set()
    folder_unknown: list = []
    sources_detail: list = []
    case_tasks: list = []
    seen_task_sigs: set = set()
    known_bytes = 0
    ok_count = 0

    for sc in subcases:
        name, path = sc.get("name", ""), sc.get("path", "")
        report = {"name": name, "path": path, "ok": False, "error": "",
                  "source_count": 0, "bytes": 0}
        if not sc.get("exists"):
            report["error"] = sc.get("error", "") or "inaccessible"
            log(f"Sous-cas ignoré « {name} » : {report['error']}")
            reports.append(report)
            continue
        # Deux écritures possibles du même sous-cas quand le compound et son
        # `<subcase>` ne nomment pas le serveur pareil (nom NetBIOS vs IP) :
        # `case_meta.read_subcases` a mis en tête celle du compound, on garde
        # l'autre en repli — une session SMB peut réussir là où l'autre échoue.
        candidates = [path]
        declared = sc.get("declared_path", "")
        if declared and declared != path:
            log(f"Sous-cas « {name} » : lu via {path} "
                f"(déclaré {declared} dans le case.xml du compound).")
            if os.path.isdir(declared):
                candidates.append(declared)

        sub_rows = sub_inv = None
        for attempt, cand in enumerate(candidates):
            if attempt:
                log(f"Nouvel essai du sous-cas « {name} » via {cand}")
            try:
                sub_rows, _cols, sub_inv = run_export_source_list(
                    exe, user, cand, log, extra_args=extra_args,
                    timeout_min=timeout_min)
            except Exception as exc:  # noqa: BLE001 — un sous-cas KO n'arrête pas les autres
                report["error"] = str(exc)
                log(f"Échec de lecture du sous-cas « {name} » : {exc}")
                sub_rows = sub_inv = None
                continue
            report["error"] = ""
            path = report["path"] = cand
            break
        if sub_inv is None:
            reports.append(report)
            continue

        ok_count += 1
        for r in sub_rows:
            merged = {SUBCASE_COLUMN: name}
            merged.update(r)
            rows.append(merged)
        for d in sub_inv.get("sources_detail", []):
            d["subcase"] = name
            d["subcase_path"] = path
            sources_detail.append(d)
        existing_paths |= sub_inv.get("existing_paths", set())
        existing_share_keys |= sub_inv.get("existing_share_keys", set())
        # Chaque dossier à 0 porte SON sous-cas : c'est là (et pas au niveau du
        # compound) que se lit et s'écrit le cache de tailles `IF_<cas>.info` —
        # un sous-cas peut être retiré du lot, ou recevoir de nouvelles sources,
        # sans que le reste de l'ensemble ait à en souffrir.
        for f in sub_inv.get("folder_unknown", []):
            f["subcase"] = name
            f["subcase_path"] = path
            f["case_name"] = sub_inv.get("case_name", "") or name
            folder_unknown.append(f)
        known_bytes += sub_inv.get("known_bytes", 0) or 0
        # Tâches : même déduplication par signature qu'au sein d'un cas simple,
        # poursuivie d'un sous-cas à l'autre (les UUID diffèrent par source).
        for obj in sub_inv.get("case_tasks", []):
            sig = _task_signature(obj)
            if sig not in seen_task_sigs:
                seen_task_sigs.add(sig)
                case_tasks.append(obj)
        if sub_inv.get("xml_path"):
            xml_paths.append(sub_inv["xml_path"])
        report.update({"ok": True, "source_count": len(sub_rows),
                       "bytes": sub_inv.get("known_bytes", 0) or 0})
        reports.append(report)

    if subcases and not ok_count:
        raise RuntimeError(
            "Aucun sous-cas n'a pu être lu (voir le journal). Vérifiez que les "
            "emplacements des sous-cas sont accessibles depuis ce poste."
        )

    inventory = {
        "case_name": case_name,
        "case_path": case_path,
        "case_path_key": _norm(case_path),
        "existing_paths": existing_paths,
        "existing_share_keys": existing_share_keys,
        "known_bytes": known_bytes,
        "folder_unknown": folder_unknown,
        "source_count": len(rows),
        "case_tasks": case_tasks,
        "sources_detail": sources_detail,
        # Un XML par sous-cas lu ; ``xml_path`` garde le premier pour les
        # appelants qui n'attendent qu'un fichier.
        "xml_paths": xml_paths,
        "xml_path": xml_paths[0] if xml_paths else "",
        "is_compound": True,
        "subcase_reports": reports,
    }
    log(f"Cas compound : {len(rows)} source(s) sur {ok_count}/{len(subcases)} sous-cas lu(s).")
    return rows, list(DISPLAY_COLUMNS_COMPOUND), inventory


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


# Balises de `<source>` qui ne sont PAS des réglages : identité de la source et
# **résultats** de l'indexation (taille, nombre de segments, tâches exécutées).
# `timeZone` est un réglage, mais il est déjà lu à part (`timezone`) et réémis
# par l'onglet Import : le compter deux fois le ferait passer pour perdu.
_SOURCE_NON_OPTION_TAGS = {
    "id", "name", "type", "timeZone", "size", "totalSize", "partsCount",
    "firstPartName", "lastPartName", "diskImagePath", "path", "tasks",
    "indexOptions", "domainBoundaries",
}


def _source_options(elem) -> dict:
    """Réglages portés par ``<source>`` lui-même, hors ``<indexOptions>``.

    Constatés sur des exports réels : ``includeHiddenResources``,
    ``carveUnallocatedSpace`` (images), ``scriptEnabled``/``scriptValidated``/
    ``scriptType``/``scriptLogEnabled``. Ils n'étaient **pas lus** jusqu'au
    10/09/2026, si bien que le décompte des réglages non rejoués annoncé à
    l'utilisateur était sous-estimé.

    ⚠ **Liste NOIRE, pas liste blanche.** On prend tout ce qui n'est pas
    identifié comme identité ou résultat : une balise ajoutée par une future
    version d'Intella doit **apparaître** (en rouge dans le visualiseur), pas
    disparaître en silence — c'est tout l'intérêt de la vue.
    """
    out = {}
    for child in elem:
        if child.tag in _SOURCE_NON_OPTION_TAGS or len(child):
            continue
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
            "source_options": _source_options(elem),
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
            taille = SIZE_UNKNOWN_LABEL
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
    # Mêmes chemins, hôte UNC neutralisé : un cas mélange les écritures (nom
    # NetBIOS et IP) et une source redéposée sous l'autre forme repartait à
    # l'import en double (08/09/2026). Cf. `path_parser.share_key`.
    existing_share_keys: set[str] = set()
    known_bytes = 0
    folder_unknown = []

    case_tasks: list = []          # définitions de tâches recyclables (dédupliquées)
    seen_task_sigs: set = set()
    for s in parsed["sources"]:
        chemins = list(s["paths"])
        if s["disk_image_path"]:
            chemins.append(s["disk_image_path"])
        if s["primary_path"]:
            chemins.append(s["primary_path"])
        for p in chemins:
            existing_paths.add(_norm(p))
            existing_share_keys.add(path_parser.share_key(p))
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
        "existing_share_keys": existing_share_keys,
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
