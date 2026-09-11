# -*- coding: utf-8 -*-
"""Traductions anglaises des clés introduites par la v3.1 (chantier UI).

Usage ponctuel : ``python outils\\_us_v31.py`` complète ``lang/US.lang`` pour les
clés qui y manquent encore, puis le test AST et ``gen_lang_data`` font le reste.
"""

import io
import json
import os
import sys

SCRIPT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

US = {
    # --- panneau de types -------------------------------------------------
    "profiles.filter_mode_label": "Type filter mode",
    "profiles.filter_mode_tip": (
        "“exclude”: the listed types are LEFT OUT, everything else is indexed.\n"
        "“include”: ONLY the listed types are indexed.\n\n"
        "It defaults to “exclude”, as in Intella: a list built as “what I want "
        "to keep” would then do the exact opposite."),
    "profiles.other_filters": "Other filters",
    "profiles.hash_filter_tip": (
        "Paths to .md5 files, comma separated. Items whose hash appears there are "
        "left out of indexing.\n"
        "⚠ The path must be reachable FROM THE INTELLA SERVER, not from this "
        "workstation."),
    "mime.states_tip": (
        "A type's state in the reference list:\n"
        "• described — label supplied by Vound;\n"
        "• described by you — label you typed;\n"
        "• seen in your cases — Intella writes it without naming it. A valid "
        "synonym, nothing to fix;\n"
        "• unknown — never encountered. Check the spelling, or your Intella is "
        "newer than the reference list."),
    "mime.only_categories_tip": (
        "Ticked: only Intella's 78 categories, all of them described — that is "
        "what a filter usually holds.\n"
        "Unticked: every type, grouped by family (application, image, text…). The "
        "family is the only membership Vound's reference list allows us to derive; "
        "it never says which Intella category a type belongs to."),
    "mime.add_to_filter": "◀ Add to filter",
    "mime.remove": "Remove",
    "mime.remove_all": "Remove all",
    "mime.describe": "Describe this type…",
    "mime.describe_title": "Describe a type",
    "mime.describe_prompt": "Your description for “{t}”:",
    "mime.describe_none": "Select a type in the list first.",
    "mime.describe_log": "Personal description: {t} → “{d}”",
    "mime.count_in_filter": "{n} type(s) in this filter",
    "mime.added_log": "{n} type(s) added to the profile filter.",
    "mime.ref_categories": "{n} categor(ies)",
    "mime.ref_types": "{n} type(s) in {f} famil(ies)",
    "mime.family_other": "(other)",
    "mime.family_count": "{n} type(s)",
    "mime.col_origin": "Comes from",
    "mime.filter_undescribed": "No description",
    "mime.filter_user": "Described by you",
    "mime.filter_external": "From an import",
    "mime.shown": "{n} type(s) shown.",
    "mime.import_tip": (
        "Adds the labels of an Intella .properties file to those already known.\n"
        "Entries of the same name are replaced by the file's; the others stay. "
        "Nothing is lost: successive imports add up into a single file."),
    "mime.learn_tip": (
        "Collects the type NAMES found in a source export, without giving them a "
        "label.\n\nWhat for: Intella writes synonyms into its filters that it "
        "describes nowhere (18 % of a real filter). Learning them keeps those "
        "names from showing as “unknown” — which would make the normal look like "
        "an anomaly."),
    "mime.origin_merged": (
        "{n} description(s) come from {f} imported file(s), added to the {e} "
        "built-in ones."),
    "mime.origin_embedded": (
        "All of them come from the version built into the application; importing "
        "an Intella .properties file would add its own."),
    "mime.import_ok": "{n} description(s) read from the file.",
    "mime.import_added": "{n} type(s) gain a label.",
    "mime.import_updated": "{n} label(s) replaced by the file's.",
    "mime.import_kept": "{n} were already identical.",
    "mime.import_total": "The reference list now holds {n} descriptions.",
    # --- visualiseur des réglages ----------------------------------------
    "settings.tip_mapped": (
        "This setting is one of the options IntellaCmd accepts on automatic "
        "import. Saved in the profile, it will be reapplied as is to every source "
        "using that profile. Nothing for you to do."),
    "settings.tip_unsupported": (
        "Intella can store this setting, but its automatic import does not accept "
        "it: the command silently drops it. A profile therefore cannot replay "
        "it.\n\nWhat to do: after the import, open the source in Intella and set "
        "it by hand — or accept the default."),
    "settings.tip_unknown": (
        "This setting name is neither in the list of drivable options nor in the "
        "list of known-but-not-replayable ones. That almost always means your "
        "Intella is newer than what the application knows about.\n\nWhat to do: "
        "check in Intella what that setting is worth for your sources. Nothing is "
        "broken."),
    # --- aide --------------------------------------------------------------
    "help.search": "Search the help",
    "help.search_clear": "Clear",
    "help.search_hits": "{n} result(s)",
    "help.search_pos": "{i} / {n}",
    "help.search_tip": (
        "Type a word: every occurrence is highlighted. “›” and “‹” jump from "
        "one to the next; Enter does the same as “›”."),
    "help.fig_step1": "① The case",
    "help.fig_step1_sub": "read what is already there",
    "help.fig_step2": "② Import sources",
    "help.fig_step2_sub": "paste → analyse → run the import",
    "help.fig_include": "ONLY these types are indexed",
    "help.fig_exclude": "these types are LEFT OUT",
    "help.fig_filter_note": ("The default is “exclude”.\nA list built as “what I "
                             "want”\nthen does the exact opposite."),
    "help.fig_first": "give this one",
    "help.fig_segments_note": ("One line to paste: the first segment. Intella "
                               "finds the others by itself."),
    # --- écran Fichiers ----------------------------------------------------
    "files.col_what": "Item",
    "files.col_where": "Location",
    "files.col_state": "State",
    "files.copy": "Copy this information",
    "files.copied": "Version information copied.",
    "files.n_files": "{n} file(s)",
    "files.n_cases": "{n} case(s)",
    "files.cases": "Generated output",
    "files.state_ok": "read at startup",
    "files.hint": ("Double-click a row to open it. A missing folder is not a "
                   "fault: it is created on first use."),
    "app.subtitle": "Intella import source generator",
    # --- import ------------------------------------------------------------
    "import.clear_all": "Clear all",
    "import.clear_all_tip": ("Clears the table AND the paths pasted above: you "
                             "start from scratch."),
    "import.clear_all_confirm": ("Start from scratch?\n\n{n} source(s) from the "
                                 "table and {c} pasted path(s) will be erased."),
    "import.clear_all_log": "Tab cleared: {n} source(s) and {c} pasted path(s).",
    "import.integrity_off": "source integrity not checked",
    "import.integrity_on": "source integrity checked",
    # --- inventaire --------------------------------------------------------
    "inventory.info_profile_tip": ("Picks up the indexing settings of the selected "
                                   "source and opens the Profiles tab to save them "
                                   "under a name."),
    "inventory.zero_folders_none": ("No folder left to measure: every volume in "
                                    "this case is known."),
    "inventory.zero_folders_unread": ("The sources of this case have not been read "
                                      "yet.\nRun “Read sources” first."),
    "inventory.export_tasks_none": "No task is defined on the sources of this case.",
    "inventory.export_tasks_unread": ("The sources of this case have not been read "
                                      "yet.\nRun “Read sources” first."),
    # --- fil d'étapes ------------------------------------------------------
    "step.sources": "Import sources",
    "step.sources_sub": "paste, measure, import",
    "tabs.import": "2. Import sources",
}


def main():
    chemin = os.path.join(SCRIPT_DIR, "lang", "US.lang")
    with io.open(chemin, encoding="utf-8") as f:
        data = json.load(f)
    n = 0
    for cle, valeur in US.items():
        if data["strings"].get(cle) != valeur:
            data["strings"][cle] = valeur
            n += 1
    with io.open(chemin, "w", encoding="utf-8", newline="\n") as f:
        json.dump(data, f, ensure_ascii=False, indent=4)
        f.write("\n")
    print("US : %d cle(s) ecrite(s), %d au total" % (n, len(data["strings"])))
    return 0


if __name__ == "__main__":
    sys.exit(main())
