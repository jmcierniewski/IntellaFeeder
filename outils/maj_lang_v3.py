# -*- coding: utf-8 -*-
"""Aligne ``lang/FR.lang`` sur les fallbacks du code, et complète ``lang/US.lang``.

Usage ponctuel du chantier v3 : le code porte désormais les textes définitifs
(FR), et ``tests/test_i18n_defaults.py`` exige que le fichier de langue les
reflète. Ce script fait donc du **code la source de vérité pour le français**,
et n'ajoute à l'anglais que les clés nouvelles, avec les traductions données
ci-dessous.

⚠ Les ``.lang`` sont en ordre **thématique**, pas alphabétique : les clés
nouvelles vont à la fin, jamais de tri (un tri ferait un diff de 500 lignes pour
une clé — cf. CLAUDE.md, section « Internationalisation »).
"""

import ast
import io
import json
import os
import sys

ICI = os.path.dirname(os.path.abspath(__file__))
SCRIPT_DIR = os.path.dirname(ICI)
IGNORES = {"lang_data.py"}

# Traductions anglaises des clés introduites par la v3.
US = {
    # --- barre de contexte ---
    "ctx.case": "CASE",
    "ctx.user": "USER",
    "ctx.exe": "INTELLACMD",
    "ctx.edit": "Edit…",
    "ctx.no_case": "no case selected",
    "ctx.exe_ok": "configured",
    "ctx.exe_missing": "not set",
    # --- fil d'étapes ---
    "step.case": "The case",
    "step.case_sub": "read what is already there",
    "step.sources": "Sources",
    "step.sources_sub": "pick and measure",
    "step.import": "Import",
    "step.import_sub": "generate and run",
    "tabs.detail_short": "Details",
    # --- import : paramètres repliés ---
    "import.params_edit": "Edit ▾",
    "import.params_close": "Collapse ▴",
    "import.integrity_off": "integrity not checked",
    "import.integrity_on": "integrity checked",
    "import.summary_case": "Target case: {n}",
    "import.summary_nocase": "none",
    "import.summary_limit": "limit {g} GB",
    "import.summary_tz": "time zone {t}",
    "import.summary_tasks": "tasks {f}",
    "import.more_tip": ("Export / import a list, reload tasks, reuse the case "
                        "tasks, clear the list"),
    "import.already_in_case": "— already in the case",
    # --- journal ---
    "journal.search": "Search",
    "journal.filter_all": "All",
    "journal.filter_alerts": "Warnings",
    "journal.filter_errors": "Errors",
    "journal.status_errors": "{e} error(s) and {a} warning(s) — see the journal",
    "journal.status_alerts": "{a} warning(s) — see the journal",
    # --- options ---
    "options.display": "Display",
    "options.language": "Language",
    "options.language_hint": "applied on restart",
    "options.density": "Display density",
    "options.density_compact": "Compact",
    "options.density_normal": "Normal",
    "options.density_comfort": "Comfortable",
    "options.font_scale": "Text size",
    "options.scale_reset": "Reset",
    "options.density_help": (
        "Density drives table row height and margins: “compact” to fit more "
        "sources on a laptop screen, “comfortable” on a large display. Both "
        "settings apply immediately."),
    "options.dnd": "Drag and drop",
    "options.dnd_enable": "Enable drag and drop from File Explorer",
    "options.dnd_help": (
        "Safety switch: when off, the application stays usable by pasting paths "
        "and by the “Add…” buttons. Takes effect on restart."),
    "options.dnd_saved": "Drag and drop: {v} (from next start).",
    # --- profils (D8 / D11) ---
    "profiles.to_verify_tip": (
        "Presumed mapping, never confirmed on a real case: check before "
        "relying on it."),
    "profiles.images_only_tip": (
        "No effect on a folder source: applies to forensic images only."),
    "profiles.images_only": "images",
}


def appels():
    """(clé, défaut FR) de tous les ``i18n.t(...)`` du code applicatif."""
    trouves = {}
    for name in sorted(os.listdir(SCRIPT_DIR)):
        if not name.endswith(".py") or name in IGNORES:
            continue
        with io.open(os.path.join(SCRIPT_DIR, name), encoding="utf-8") as f:
            arbre = ast.parse(f.read(), filename=name)
        for node in ast.walk(arbre):
            if not isinstance(node, ast.Call) or len(node.args) < 2:
                continue
            func = node.func
            if not (isinstance(func, ast.Attribute) and func.attr == "t"
                    and isinstance(func.value, ast.Name) and func.value.id == "i18n"):
                continue
            k, d = node.args[0], node.args[1]
            if not (isinstance(k, ast.Constant) and isinstance(k.value, str)):
                continue
            try:
                defaut = ast.literal_eval(d)
            except (ValueError, SyntaxError):
                continue
            if isinstance(defaut, str):
                trouves[k.value] = defaut
    return trouves


def charger(code):
    chemin = os.path.join(SCRIPT_DIR, "lang", f"{code}.lang")
    with io.open(chemin, encoding="utf-8") as f:
        return chemin, json.load(f)


def ecrire(chemin, data):
    with io.open(chemin, "w", encoding="utf-8", newline="\n") as f:
        json.dump(data, f, ensure_ascii=False, indent=4)
        f.write("\n")


def main():
    code_fr = appels()
    chemin_fr, fr = charger("FR")
    chemin_us, us = charger("US")

    ajoutees, majs = [], []
    for cle, defaut in code_fr.items():
        if cle not in fr["strings"]:
            fr["strings"][cle] = defaut
            ajoutees.append(cle)
        elif fr["strings"][cle] != defaut:
            fr["strings"][cle] = defaut
            majs.append(cle)

    manquantes_us = []
    for cle in code_fr:
        if cle in us["strings"]:
            continue
        if cle in US:
            us["strings"][cle] = US[cle]
        else:
            # Repli explicite plutôt que silencieux : une clé anglaise laissée
            # en français se verra tout de suite à l'écran.
            us["strings"][cle] = code_fr[cle]
            manquantes_us.append(cle)

    ecrire(chemin_fr, fr)
    ecrire(chemin_us, us)
    print(f"FR : {len(ajoutees)} ajoutée(s), {len(majs)} mise(s) à jour "
          f"→ {len(fr['strings'])} clés")
    print(f"US : {len(us['strings'])} clés")
    if manquantes_us:
        print("⚠ sans traduction anglaise (restées en FR) :")
        for c in manquantes_us:
            print("   ", c)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
