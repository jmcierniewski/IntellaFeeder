"""Constantes, résolution de chemins (PyInstaller) et utilitaires partagés."""

import os
import sys
from datetime import datetime

APP_NAME = "IntellaFeeder"
APP_VERSION = "2.4"
APP_TITLE = "IntellaFeeder — Générateur de sources d'import Intella"

# --- Réglages forensiques par défaut ---
DEFAULT_TIMEZONE = "UTC"
TIMEZONES = ["UTC", "Europe/Paris", "CET"]

# --- Garde-fou taille de cas (l'UI Intella bloque > 1 To) ---
DEFAULT_SIZE_LIMIT_GB = 950
GB = 1024 ** 3  # 1 Go binaire

# --- Types de source IntellaCmd ---
SOURCE_TYPE_DISK_IMAGE = "DISK_IMAGE"
SOURCE_TYPE_FOLDER = "FOLDER_OR_FILE"
TYPE_LABELS = {
    SOURCE_TYPE_DISK_IMAGE: "Image",
    SOURCE_TYPE_FOLDER: "Dossier",
}


def type_label(source_type: str) -> str:
    """Libellé traduit d'un type de source (import tardif, cf. ``human_size``)."""
    import i18n
    key = {"DISK_IMAGE": "type.image", "FOLDER_OR_FILE": "type.folder"}.get(source_type)
    return i18n.t(key, TYPE_LABELS.get(source_type, source_type)) if key else source_type

# --- Fichiers produits ---
SOURCES_JSON = "sources.json"
BAT_NAME = "import_intella.bat"
DEFAULT_TASKS_FILENAME = "tasks.json"
INI_NAME = "intellafeeder.ini"

# --- Arborescence de sortie : Script\Cas\<nom du cas>\{scripts,logs} ---
CAS_DIRNAME = "Cas"
SCRIPTS_DIRNAME = "scripts"
LOGS_DIRNAME = "logs"

# --- Profils de paramètres d'analyse : 1 fichier JSON par profil ---
PROFILS_DIRNAME = "profils"

# --- Langues de l'interface : 1 fichier JSON (.lang) par langue ---
LANG_DIRNAME = "lang"

# --- Glyphes des cases à cocher ---
CHECK = "☑"
UNCHECK = "☐"

# --- Couleurs d'onglets (pastilles + boutons « cross-onglet ») ---
INVENTORY_TAB_COLOR = "#3b82f6"   # onglet « 1. Inventaire du cas »
PROFILE_TAB_COLOR = "#8b5cf6"     # onglet « Profils » (bouton « Info Profil »)


def glyph(state: bool) -> str:
    return CHECK if state else UNCHECK


def base_dir() -> str:
    """Dossier de l'exécutable (frozen) ou du script (source)."""
    if getattr(sys, "frozen", False):
        return os.path.dirname(sys.executable)
    return os.path.dirname(os.path.abspath(__file__))


def resource_path(name: str) -> str:
    """Ressource embarquée en lecture seule (PyInstaller _MEIPASS), sinon base_dir."""
    if getattr(sys, "frozen", False) and hasattr(sys, "_MEIPASS"):
        candidate = os.path.join(sys._MEIPASS, name)
        if os.path.exists(candidate):
            return candidate
    return os.path.join(base_dir(), name)


def default_tasks_path() -> str:
    return os.path.join(base_dir(), DEFAULT_TASKS_FILENAME)


# --- Horodatage local (= Romance Standard Time sur la station FR) ---
try:
    from zoneinfo import ZoneInfo  # stdlib 3.9+

    _TZ = ZoneInfo("Europe/Paris")
except Exception:  # tzdata absent sous Windows : on retombe sur l'heure locale
    _TZ = None


def now_str(fmt: str = "%Y-%m-%d %H:%M:%S") -> str:
    """Horodatage courant fuseau FR (ou heure locale machine en repli)."""
    if _TZ is not None:
        return datetime.now(_TZ).strftime(fmt)
    return datetime.now().strftime(fmt)


def now_compact() -> str:
    """Groupe date-heure compact pour noms de fichiers (yyyyMMdd_HHmm)."""
    return now_str("%Y%m%d_%H%M")


def human_size(num_bytes: int) -> str:
    """Taille lisible (Go/Mo — unité traduite ; import tardif pour éviter le
    cycle avec ``i18n`` qui importe ``config``)."""
    import i18n
    if num_bytes >= GB:
        return f"{num_bytes / GB:.2f} " + i18n.t("unit.gb", "Go")
    return f"{num_bytes / (1024 ** 2):.1f} " + i18n.t("unit.mb", "Mo")


def epoch_ms_to_str(ms: int, fmt: str = "%Y-%m-%d %H:%M") -> str:
    """Convertit un horodatage epoch en millisecondes (case.xml) en date FR lisible."""
    if not ms:
        return "—"
    try:
        if _TZ is not None:
            return datetime.fromtimestamp(ms / 1000, _TZ).strftime(fmt)
        return datetime.fromtimestamp(ms / 1000).strftime(fmt)
    except (ValueError, OSError, OverflowError):
        return "—"


def sanitize_filename(name: str) -> str:
    """Nom de fichier/dossier sûr : caractères interdits et espaces → '_'."""
    import re
    s = re.sub(r'[<>:"/\\|?*\x00-\x1f]+', "_", name or "")
    s = re.sub(r"\s+", "_", s).strip("._ ")
    return s or "Case"


def case_dir(case_name: str) -> str:
    """Dossier de sortie d'un cas : ``base\\Cas\\<nom assaini>``."""
    return os.path.join(base_dir(), CAS_DIRNAME, sanitize_filename(case_name))


def case_scripts_dir(case_name: str) -> str:
    return os.path.join(case_dir(case_name), SCRIPTS_DIRNAME)


def case_logs_dir(case_name: str) -> str:
    return os.path.join(case_dir(case_name), LOGS_DIRNAME)


def profiles_dir() -> str:
    """Dossier des profils (``base\\profils``), partagé entre tous les cas."""
    return os.path.join(base_dir(), PROFILS_DIRNAME)


def lang_dir() -> str:
    """Dossier des fichiers de langue (``base\\lang``)."""
    return os.path.join(base_dir(), LANG_DIRNAME)
