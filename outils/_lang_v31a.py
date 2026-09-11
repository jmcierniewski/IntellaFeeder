# -*- coding: utf-8 -*-
"""Clés de langue du lot v3.1a (réglages d'ergonomie du 11/09/2026, 2e passe).

Usage ponctuel : ``python outils\\_lang_v31a.py`` met à jour ``lang/FR.lang`` et
``lang/US.lang``, puis ``outils\\gen_lang_data.py`` régénère l'embarqué.

⚠ Les ``.lang`` sont en ordre **thématique** : on écrit par ``update`` (les
nouvelles clés vont à la fin), jamais par un tri.
"""

import io
import json
import os
import sys

SCRIPT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

FR = {
    # « vu dans vos cas » laissait croire que le type était dans le cas COURANT.
    "mime.state_observed": "connu, sans libellé",
    "mime.filter_summary": "{t} type(s) — {d} décrit(s), {o} sans libellé",
    "mime.state": ("{d} descriptions (dont {c} catégories) — {o} nom(s) de type "
                   "connu(s), dont {s} sans description."),
    "mime.states_tip": (
        "État d'un type dans le référentiel :\n"
        "• décrit — libellé fourni par Vound ;\n"
        "• décrit par vous — libellé que vous avez saisi ;\n"
        "• connu, sans libellé — le nom existe (Intella l'écrit), mais personne "
        "ne le décrit. C'est un synonyme valide, il n'y a rien à corriger ;\n"
        "• inconnu — jamais rencontré. Vérifiez l'orthographe, ou votre version "
        "d'Intella est plus récente que le référentiel."),
    "mime.pane_current": "Types inclus dans ce filtre",
    "mime.catalog_tip": (
        "Double-cliquez un type pour l'ajouter au filtre, à gauche (sélection "
        "multiple possible, puis « ◀ Ajouter au filtre »).\n"
        "Un double-clic sur une famille l'ouvre ou la referme.\n\n"
        "Pour donner un libellé à un type, passez par Maintenance → Types MIME."),
    "inventory.grp_profile": "Reprendre",
}

US = {
    "mime.state_observed": "known, no label",
    "mime.filter_summary": "{t} type(s) — {d} described, {o} without a label",
    "mime.state": ("{d} descriptions ({c} categories) — {o} known type name(s), "
                   "{s} of them without a description."),
    "mime.states_tip": (
        "A type's state in the reference list:\n"
        "• described — label supplied by Vound;\n"
        "• described by you — label you typed;\n"
        "• known, no label — the name exists (Intella writes it), but nobody "
        "describes it. A valid synonym, nothing to fix;\n"
        "• unknown — never encountered. Check the spelling, or your Intella is "
        "newer than the reference list."),
    "mime.pane_current": "Types included in this filter",
    "mime.catalog_tip": (
        "Double-click a type to add it to the filter on the left (you can also "
        "select several, then “◀ Add to filter”).\n"
        "Double-clicking a family folds or unfolds it.\n\n"
        "To give a type a label, go to Maintenance → MIME types."),
    "inventory.grp_profile": "Reuse",
}


def _ecrire(code, table):
    chemin = os.path.join(SCRIPT_DIR, "lang", "%s.lang" % code)
    with io.open(chemin, encoding="utf-8") as f:
        data = json.load(f)
    n = 0
    for cle, valeur in table.items():
        if data["strings"].get(cle) != valeur:
            data["strings"][cle] = valeur
            n += 1
    with io.open(chemin, "w", encoding="utf-8", newline="\n") as f:
        json.dump(data, f, ensure_ascii=False, indent=4)
        f.write("\n")
    print("%s : %d cle(s) ecrite(s), %d au total"
          % (code, n, len(data["strings"])))


def main():
    _ecrire("FR", FR)
    _ecrire("US", US)
    return 0


if __name__ == "__main__":
    sys.exit(main())
