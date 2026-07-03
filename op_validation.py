"""Analyse des logs d'import produits par le .bat résilient.

Chaque source importée écrit un log dans ``Cas\\<nom>\\logs\\``. On le lit pour
déterminer si l'ajout a réussi (« Added new source ») ou échoué (validation,
exception, usage réaffiché…), et on en extrait le chemin d'évidence et le motif.

Complète le re-scan du cas (``-exportSourceList``) : le re-scan dit *ce qui est
dans le cas*, le log dit *pourquoi* une source manque le cas échéant.
"""

import os
import re

import i18n

# Sous-dossier de run : groupe date-heure yyyyMMdd_HHmm (cf. generator).
_RUN_RE = re.compile(r"^\d{8}_\d{4}$")
_RE_ADDED = re.compile(r"Added new source:\s*(.+?)\s*(?:\[urn:uuid|$)", re.IGNORECASE)
# Lignes de bootstrap logback (ex. "14:34:44,187 |-INFO in ch.qos.logback...
# - Could NOT find resource [logback-test.scmo]") : toujours présentes, jamais
# une erreur d'import (cf. réponse support Vound).
_RE_LOGBACK_BOOT = re.compile(r"ch\.qos\.logback", re.IGNORECASE)
_FAIL_MARKERS = (
    "validation failed",
    "error validating",
    "exception",
    "failed",
    "could not",
    "usage: intellacmd",
)


def parse_import_log(path: str) -> dict:
    """Analyse un fichier log → ``{ok, evidence, message}``.

    ``ok`` : True si la source a été ajoutée. ``evidence`` : chemin ajouté (si vu).
    ``message`` : 1ʳᵉ ligne d'erreur significative (si échec).
    """
    added = None
    fail_line = None
    try:
        with open(path, encoding="utf-8", errors="replace") as f:
            for line in f:
                line = line.rstrip()
                m = _RE_ADDED.search(line)
                if m:
                    added = m.group(1).strip()
                    continue
                if _RE_LOGBACK_BOOT.search(line):
                    # Bootstrap logback (recherche de logback.xml/.scmo absents,
                    # normal à chaque lancement) : jamais une erreur d'import.
                    continue
                low = line.lower()
                if fail_line is None and any(mk in low for mk in _FAIL_MARKERS):
                    fail_line = line.strip()
    except OSError as exc:
        return {"ok": False, "evidence": None,
                "message": i18n.t("op_validation.log_unreadable", "Log illisible : {e}", e=exc)}

    if added and not fail_line:
        return {"ok": True, "evidence": added, "message": ""}
    if added and fail_line:
        # Ajout vu mais une erreur ensuite : on signale les deux.
        return {"ok": True, "evidence": added,
                "message": i18n.t("op_validation.added_but", "Ajout OK mais : {m}", m=fail_line)}
    return {"ok": False, "evidence": None,
            "message": fail_line or i18n.t(
                "op_validation.no_confirmation", "Aucune confirmation d'ajout dans le log.")}


def list_runs(logs_dir: str) -> list[str]:
    """Sous-dossiers de run (yyyyMMdd_HHmm) triés du plus ancien au plus récent."""
    if not os.path.isdir(logs_dir):
        return []
    runs = [d for d in os.listdir(logs_dir)
            if _RUN_RE.match(d) and os.path.isdir(os.path.join(logs_dir, d))]
    return sorted(runs)


def latest_run_dir(logs_dir: str) -> str:
    """Dossier du run le plus récent à analyser.

    Retourne le sous-dossier horodaté le plus récent ; à défaut (ancien format
    plat, sans sous-dossier) retourne ``logs_dir`` tel quel.
    """
    runs = list_runs(logs_dir)
    return os.path.join(logs_dir, runs[-1]) if runs else logs_dir


def scan_logs(logs_dir: str) -> list[dict]:
    """Analyse tous les ``.log`` d'un dossier → liste ``{file, ok, evidence, message}``."""
    results = []
    if not os.path.isdir(logs_dir):
        return results
    for name in sorted(os.listdir(logs_dir)):
        if not name.lower().endswith(".log"):
            continue
        path = os.path.join(logs_dir, name)
        info = parse_import_log(path)
        info["file"] = name
        results.append(info)
    return results
