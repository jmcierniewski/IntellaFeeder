# -*- coding: utf-8 -*-
"""Script de fumée du chantier v3 : ouvre l'application sur un écran donné.

**Pourquoi un script plutôt qu'un test pytest** : la suite ne couvre que les
modules sans interface (cf. CLAUDE.md, section « Tests »). Une fenêtre réelle se
vérifie à l'œil, et c'est ce genre de script qui a attrapé les vrais défauts de
la v2.6 (``hasattr(import_tab)``) comme de la v3.0 (polices nommées libérées par
le ramasse-miettes).

    python tests\\manuel_fumee_v3.py [ecran] [--secondes N] [--densite compacte]

``ecran`` : inventaire | detail | import | profils | maintenance | aide
            | profils-types | options | mime | fichiers | reglages

Sans argument : reste ouvert sur l'Inventaire jusqu'à fermeture manuelle.
Avec ``--secondes``, la fenêtre se referme seule (capture d'écran scriptée).
"""

import os
import sys
import tkinter as tk

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import ui_theme                                        # noqa: E402
from ui import MainWindow                              # noqa: E402


def _sous_onglet(app, parent, enfant):
    app.aller_a(parent)
    parent.notebook.select(enfant)


ECRANS = {
    "inventaire": lambda a: a._on_nav_select("inventaire", 0),
    "detail": lambda a: a._on_nav_select("detail"),
    "import": lambda a: a._on_nav_select("import", 1),
    "profils": lambda a: a._on_nav_select("profils"),
    "profils-types": lambda a: (a._on_nav_select("profils"),
                                a.profiles_tab.subnotebook.select(
                                    a.profiles_tab.types_panel)),
    "maintenance": lambda a: a._on_nav_select("maintenance"),
    "options": lambda a: _sous_onglet(a, a.maintenance_tab, a.maintenance_tab.options_tab),
    "mime": lambda a: _sous_onglet(a, a.maintenance_tab, a.maintenance_tab.mime_tab),
    "fichiers": lambda a: _sous_onglet(a, a.maintenance_tab, a.maintenance_tab.files_tab),
    "aide": lambda a: a._on_nav_select("aide"),
    "reglages": lambda a: _reglages(a),
}


def _reglages(app):
    """Ouvre « Voir les réglages de la source… » sur une source FABRIQUÉE.

    Cette fenêtre s'est ouverte **vide** pendant une journée (constante de
    couleurs disparue, cf. `ui_widgets`) : elle mérite un écran à elle, sinon
    plus personne ne la regarde. Les réglages ci-dessous couvrent les trois
    états — rejoué, à refaire dans Intella, inconnu.
    """
    import ui_widgets
    src = {
        "name": "SCELLE_01_PC_BUREAU.E01",
        "index_options": {
            "indexArchives": "true", "indexMailContainers": "true",
            "indexChats": "false", "recoverDeleted": "true",
            "analyzeParagraphs": "false", "crawlerMaxBinarySize": "52428800",
            "determineEmailGeoIp": "true", "indexEmbedded": "true",
            "cacheOriginalEvidence": "false",
            "isReindexingAllowed": "false",      # connu, non rejouable
            "includeHiddenResources": "true",    # connu, non rejouable
            "iFeederOptionDeDemain": "42",       # inconnu : Intella plus récent
        },
        "source_options": {"carveUnallocatedSpace": "true"},
    }
    ui_widgets.show_source_settings(app.root, src,
                                    "Réglages de « %s »" % src["name"])


def _peupler(app):
    """Remplit l'onglet Import de sources FICTIVES, pour une capture parlante.

    ⚠ Données inventées de bout en bout : aucun nom, chemin ou volume d'un cas
    réel ne doit apparaître sur une capture destinée à sortir du poste.
    """
    import models
    BS = chr(92)
    SAUT = chr(10)
    noms = [("SCELLE_01_PC_BUREAU.E01", "DISK_IMAGE", 195_000_000_000),
            ("SCELLE_02_NAS_COMPTA.E01", "DISK_IMAGE", 103_000_000_000),
            ("MSG_ARCHIVE_DIRECTION.ad1", "DISK_IMAGE", 40_800_000_000),
            ("MSG_ARCHIVE_ATELIER.ad1", "DISK_IMAGE", 29_900_000_000),
            ("TEL_SCELLE_07_RAPPORT", "FOLDER_OR_FILE", 13_300_000_000),
            ("DOCS_SAISIE_BUREAU_A", "FOLDER_OR_FILE", 2_400_000_000),
            ("EXPORT_COMPTA_2026", "FOLDER_OR_FILE", 4_300_000_000),
            ("SCELLE_11_PORTABLE_DG.E01", "DISK_IMAGE", 26_400_000_000)]
    sources = []
    for nom, type_, taille in noms:
        racine = (BS * 2) + "SERVEUR_CAS" + BS + "partage" + BS + "D12" + BS
        s = models.Source(name=nom, source_type=type_, path=racine + nom)
        s.size_bytes = taille
        s.import_selected = True
        sources.append(s)
    app.import_tab.sources = sources
    app.import_tab.txt_images.insert("1.0", SAUT.join(
        s.path for s in sources if s.source_type == "DISK_IMAGE"))
    app.import_tab.txt_folders.insert("1.0", SAUT.join(
        s.path for s in sources if s.source_type != "DISK_IMAGE"))
    app.import_tab._refresh_tree()
    app.profiles_tab.types_panel.set_filter_text(
        "category/documents,category/office365,application/pdf,application/msword")


def main(argv):
    ecran = "inventaire"
    secondes = 0
    densite = None
    demo = False
    langue = None
    args = list(argv)
    while args:
        a = args.pop(0)
        if a == "--secondes" and args:
            secondes = float(args.pop(0))
        elif a == "--densite" and args:
            densite = args.pop(0)
        elif a == "--langue" and args:
            langue = args.pop(0)
        elif a == "--demo":
            demo = True
        elif not a.startswith("--"):
            ecran = a
    if ecran not in ECRANS:
        print("écran inconnu :", ecran, "→", ", ".join(sorted(ECRANS)))
        return 2

    # ⚠ La langue se force AVANT la construction : les widgets ne sont pas
    # retraduits à chaud (limite tkinter assumée). Et elle se force en
    # DÉTOURNANT `i18n.load` : `MainWindow._init_language` lit le `.ini` et
    # écraserait un simple `load()` préalable. On ne touche pas au `.ini` de
    # l'utilisateur pour une capture.
    if langue:
        import i18n                                    # noqa: E402
        _vrai_load = i18n.load
        i18n.load = lambda _c=None, _v=_vrai_load, _l=langue: _v(_l)

    root = tk.Tk()
    app = MainWindow(root)
    if langue:
        i18n.load = _vrai_load
    if densite:
        app.theme.set_density(densite)
    if demo:
        _peupler(app)
    # Quelques lignes de journal pour que les filtres et la barre d'état aient
    # de quoi montrer — un écran vide ne prouverait rien.
    app.log.log("Démonstration : lecture du cas simulée.")
    app.log.log("Écart de cohérence des tailles : à confirmer.", "WARN")
    app.log.log("Sous-cas injoignable : partage non monté.", "ERROR")

    root.after(200, lambda: ECRANS[ecran](app))
    if secondes:
        root.after(int(secondes * 1000), root.destroy)
    root.mainloop()
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
