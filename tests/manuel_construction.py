# -*- coding: utf-8 -*-
"""Construit la fenêtre entière **sans l'afficher**, et vérifie ce qu'on peut.

**Pourquoi sans l'afficher.** Le script de fumée ouvre une vraie fenêtre, ce qui
vole le focus : inutilisable quand quelqu'un travaille sur le poste (règle du
CLAUDE.md global — « un poste où quelqu'un travaille est un mauvais banc de
mesure »). Ici la racine est retirée de l'écran (``withdraw``) dès sa création :
tous les widgets sont bel et bien construits, et une erreur de construction —
la catégorie de défaut que ``py_compile`` ne voit jamais — sort en code 1.

Ce que ce script NE remplace pas : le contrôle à l'œil. Il dit que ça tient
debout, pas que c'est lisible.

    python tests\\manuel_construction.py
"""

import os
import sys
import tkinter as tk

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# La console Windows est en cp1252 : « ▾ », « ◀ » ou « ⋯ » y lèvent un
# UnicodeEncodeError et **interrompent le contrôle en plein milieu**, ce qui se
# lit comme une panne de l'application. On dégrade l'affichage, pas le verdict.
for flux in (sys.stdout, sys.stderr):
    try:
        flux.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, ValueError):
        pass


def main() -> int:
    import ui_theme
    from ui import MainWindow

    root = tk.Tk()
    root.withdraw()                                   # jamais à l'écran
    ok, soucis = True, []
    try:
        app = MainWindow(root)
    except Exception as exc:                          # noqa: BLE001
        print("ÉCHEC de construction :", type(exc).__name__, exc)
        import traceback
        traceback.print_exc()
        root.destroy()
        return 1
    root.withdraw()                                   # `state("zoomed")` la remontre

    def verifie(libelle, condition, detail=""):
        nonlocal ok
        if condition:
            print(f"  ok   {libelle}")
        else:
            ok = False
            soucis.append(libelle)
            print(f"  KO   {libelle} {detail}")

    print("Construction de la fenêtre : OK")
    print()
    print("Navigation")
    verifie("deux étapes dans le fil", len(app.nav._steps) == 2)
    verifie("quatre outils à droite", len(app.nav._tools) == 4)
    verifie("six pages dans le Notebook", len(app.notebook.tabs()) == 6)

    print("Barre de contexte")
    # 🐞 Constaté en réel sur la v3.1b : en changeant de cas sans fermer
    # l'application, la ligne du haut gardait le chemin du cas PRÉCÉDENT — la
    # barre lisait `meta["path"]`, qui n'existe pas (c'est `folder`), et
    # retombait sur `last_case` du .ini.
    _last_case = app.settings.get("last_case", "")   # remis en place après coup
    app.settings.set("last_case", r"D:\ANCIEN\Cas precedent")
    xml_factice ={"id": "", "name": "Cas courant", "description": "",
                   "timestamp": 0, "lastOpened": 0, "user": "u", "size": 0,
                   "originalVersion": "", "caseVersion": "", "compound": False,
                   "subcase_paths": []}
    app.set_case_meta({"folder": r"D:\NOUVEAU\Cas courant", "name": "Cas courant",
                       "user": "u", "size": 0, "is_compound": False,
                       "subcases": [], "authorized_users": [], "optimization": "",
                       "xml": xml_factice, "prefs": {}, "tasks2": []})
    verifie("le chemin affiché est celui du cas courant, pas du précédent",
            "Cas courant" in app.context_bar.lbl_path.cget("text"),
            f"(affiché : {app.context_bar.lbl_path.cget('text')!r})")
    app.clear_case_meta()
    app.settings.set("last_case", _last_case)   # rien n'est écrit au .ini ici

    print("Onglet Import")
    imp = app.import_tab
    verifie("bouton « Tout vider » présent", hasattr(imp, "btn_clear_all"))
    verifie("paramètres repliés au départ", imp._params_open is False)
    verifie("menu « Plus ▾ » construit", hasattr(imp, "more_menu"))
    verifie("« Plus ▾ » rangé avec les autres, pas collé au bord droit",
            imp.btn_more.pack_info().get("side") == "left",
            f"(côté : {imp.btn_more.pack_info().get('side')})")
    verifie("plus de focus_action (étape 3 retirée)",
            not hasattr(imp, "focus_action"))

    print("Onglet Profils")
    prof = app.profiles_tab
    verifie("panneau de types présent", hasattr(prof, "types_panel"))
    verifie("sous-onglet « Référentiel » retiré",
            len(prof.subnotebook.tabs()) == 2,
            f"({len(prof.subnotebook.tabs())} sous-onglets)")
    verifie("plus de sélecteur de catégories", not hasattr(prof, "picker"))
    for cle in ("sourceTypeFilter", "sourceTypeFilterMode",
                "sourceHashFilters", "fileNameFilters"):
        verifie(f"clé « {cle} » enregistrée",
                cle in prof.vars or cle in prof._text_widgets)

    print("Aller-retour du filtre de types")
    panneau = prof.types_panel
    panneau.set_filter_text("category/documents,application/pdf")
    verifie("le panneau relit ce qu'on lui donne",
            panneau.get_filter_text() == "category/documents,application/pdf")
    verifie("le profil reçoit la valeur",
            prof._get_option("sourceTypeFilter") ==
            "category/documents,application/pdf",
            f"(lu : {prof._get_option('sourceTypeFilter')!r})")
    panneau._filtre_courant.append("image/jpeg")
    panneau._refresh_filtre()
    verifie("un ajout dans le panneau atteint le profil",
            "image/jpeg" in prof._get_option("sourceTypeFilter"))

    print("Panneau de types — ce que le mode dit, et de quelle couleur")
    import config
    panneau.var_mode.set("exclude")
    rouge = str(panneau.lbl_sens.cget("foreground"))
    panneau.var_mode.set("include")
    vert = str(panneau.lbl_sens.cget("foreground"))
    verifie("« exclude » en rouge", rouge == config.DANGER_COLOR, f"({rouge})")
    verifie("« include » au vert d'Enregistrer", vert == config.ACTION_COLOR,
            f"({vert})")
    verifie("plus de « Décrire ce type… » dans les profils",
            not any("crire" in str(b.cget("text")) for b in panneau._boutons),
            "(il n'a qu'un point d'entrée : Maintenance)")
    verifie("le pied du référentiel est bien un pied",
            panneau.lbl_ref.master.pack_info().get("side") == "bottom")
    panneau.set_editable(False)
    panneau._filtre_courant = []
    panneau._ajouter()
    verifie("un profil en lecture seule refuse l'ajout au double-clic",
            panneau.get_filter_text() == "")
    panneau.set_editable(True)

    print("Réglages d'une source (la fenêtre « Voir les réglages… »)")
    import profile_translate
    import ui_widgets
    verifie("les trois états ont leur couleur",
            set(ui_widgets.SETTING_STATUS_COLORS) == {
                profile_translate.STATUS_MAPPED,
                profile_translate.STATUS_UNSUPPORTED,
                profile_translate.STATUS_UNKNOWN})

    print("Maintenance")
    verifie("langue non vide dans Options",
            bool(app.maintenance_tab.options_tab.var_lang.get()))
    # Diagnostic : décoché par défaut — coché, IntellaCmd journalise les chemins
    # des pièces dans un journal exportable.
    verifie("journalisation détaillée d'IntellaCmd décochée par défaut",
            app.maintenance_tab.options_tab.var_debug.get() is False)
    verifie("référentiel listé au chargement",
            len(app.maintenance_tab.mime_tab.tree.get_children()) > 100)
    verifie("écran Fichiers rempli",
            len(app.maintenance_tab.files_tab.tree.get_children()) >= 5)

    print("Journal")
    app.log.log("bloc IntellaCmd :\nligne deux avec MOTIFRARE\nligne trois")
    j = app.journal_tab
    j.var_query.set("motifrare")
    j._on_search()
    lignes = j.text.get("1.0", "end").strip().splitlines()
    verifie("la recherche ne rend que la ligne qui correspond",
            len(lignes) == 1 and "MOTIFRARE" in lignes[0],
            f"({len(lignes)} ligne(s))")

    root.destroy()
    print()
    if ok:
        print("TOUT EST VERT")
        return 0
    print("POINTS EN ÉCHEC :", ", ".join(soucis))
    return 1


if __name__ == "__main__":
    sys.exit(main())
