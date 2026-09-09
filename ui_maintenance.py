"""Onglet **Maintenance** : ce qu'on utilise rarement, hors parcours d'import.

Un ``ttk.Notebook`` **imbriqué** (idée de l'utilisateur, 08/09/2026) plutôt qu'un
onglet de plus au premier niveau : la barre principale grossissait à chaque
ajout. Le Journal y descend — on le consulte après coup —, l'Aide reste au
premier niveau : on la cherche quand on est perdu, l'enterrer d'un cran la
rendrait introuvable.

Sous-onglets : **Journal**, **Types MIME** (référentiel d'Intella), **Fichiers**
(emplacements et version).

⚠ Sélectionner un onglet qui vit ici demande de sélectionner **le parent puis
l'enfant** : passer par ``MainWindow.aller_a()``, jamais par un
``notebook.select()`` direct.
"""

import os
import subprocess
import tkinter as tk
from tkinter import filedialog, messagebox, ttk

import config
import i18n
import mime_catalog
from ui_journal import JournalTab
from ui_widgets import MIME_STATUS_COLORS, make_button, mime_status_label


class MaintenanceTab(ttk.Frame):
    def __init__(self, parent, app):
        super().__init__(parent)
        self.app = app

        nb = ttk.Notebook(self)
        self.notebook = nb
        nb.pack(fill="both", expand=True, padx=4, pady=4)

        self.journal_tab = JournalTab(nb, app)
        self.options_tab = OptionsTab(nb, app)
        self.mime_tab = MimeTab(nb, app)
        self.files_tab = FilesTab(nb, app)

        nb.add(self.journal_tab, text=" " + i18n.t("tabs.journal", "Journal"))
        nb.add(self.options_tab, text=" " + i18n.t("tabs.options", "Options"))
        nb.add(self.mime_tab, text=" " + i18n.t("tabs.mime", "Types MIME"))
        nb.add(self.files_tab, text=" " + i18n.t("tabs.files", "Fichiers"))

    def select_child(self, widget) -> bool:
        """Affiche un de mes sous-onglets. Retourne False si ce n'est pas le mien."""
        if str(widget) not in self.notebook.tabs():
            return False
        self.notebook.select(widget)
        return True


class OptionsTab(ttk.Frame):
    """Préférences durables, mémorisées au `.ini`.

    Ce qui a sa place ici : un réglage qu'on pose **une fois** et qui vaut pour
    toutes les sessions. Ce qui n'y a pas sa place : ce qui se décide au coup
    par coup — la case « Explorer les sous-dossiers » de l'Import reste
    décochable à chaque dépôt, on ne fixe ici que sa **position de départ**.
    """

    def __init__(self, parent, app):
        super().__init__(parent)
        self.app = app

        box = ttk.LabelFrame(self, text=i18n.t("options.import", "Import de sources"))
        box.pack(fill="x", padx=10, pady=10)

        self.var_recursive = tk.BooleanVar(
            value=app.settings.get("recursive_default", "0").strip()
            in ("1", "true", "oui", "vrai"))
        ttk.Checkbutton(
            box, variable=self.var_recursive,
            command=self._save_recursive,
            text=i18n.t("options.recursive_default",
                        "Explorer les sous-dossiers par défaut (dépôt d'images "
                        "forensiques)")).pack(anchor="w", padx=8, pady=(8, 2))
        ttk.Label(box, wraplength=880, justify="left", foreground="#475569",
                  text=i18n.t(
                      "options.recursive_help",
                      "Décoché, un dossier déposé n'est exploré qu'au premier niveau : "
                      "un dossier de scellés voisine souvent avec d'autres cas ou des "
                      "copies de travail, et descendre d'office ramènerait des images "
                      "étrangères. Coché si vos images sont systématiquement rangées "
                      "dans des sous-dossiers. La case reste modifiable à chaque dépôt "
                      "dans l'onglet Import.")).pack(anchor="w", padx=8, pady=(0, 8))

    def _save_recursive(self):
        valeur = "1" if self.var_recursive.get() else "0"
        self.app.settings.set("recursive_default", valeur)
        self.app.settings.save()
        # Applique tout de suite à l'onglet Import : attendre le redémarrage
        # ferait croire que le réglage n'a pas été pris.
        if hasattr(self.app, "import_tab"):
            self.app.import_tab.var_recursive.set(self.var_recursive.get())
        self.app.log.log(i18n.t("options.recursive_saved",
                                "Exploration récursive par défaut : {v}.",
                                v=i18n.t("common.yes", "oui") if self.var_recursive.get()
                                else i18n.t("common.no", "non")))


class MimeTab(ttk.Frame):
    """Référentiel des types MIME : état, import, recherche.

    Rien n'est livré avec l'application — le fichier de descriptions appartient
    à Vound et se trouve dans l'installation d'Intella. C'est donc ici que le
    référentiel s'amorce, et ici qu'on le remplace quand Intella change de
    version.
    """

    def __init__(self, parent, app):
        super().__init__(parent)
        self.app = app

        intro = ttk.Label(self, wraplength=900, justify="left", text=i18n.t(
            "mime.intro",
            "Les filtres de types d'une source sont des listes de noms techniques "
            "— souvent plusieurs centaines. Le fichier de descriptions livré avec "
            "Intella (mimetype-descriptions_<langue>.properties, dans son dossier "
            "d'installation) permet de les afficher en clair."))
        intro.pack(fill="x", padx=10, pady=(10, 6))

        bar = ttk.Frame(self)
        bar.pack(fill="x", padx=10, pady=(0, 6))
        make_button(bar, i18n.t("mime.import", "Importer un fichier de descriptions…"),
                    self._import).pack(side="left")
        make_button(bar, i18n.t("mime.learn_xml", "Apprendre depuis un export XML…"),
                    self._learn_xml).pack(side="left", padx=6)
        make_button(bar, i18n.t("mime.open_folder", "Ouvrir le dossier"),
                    lambda: open_folder(config.mime_dir())).pack(side="left")

        self.lbl_state = ttk.Label(self, justify="left")
        self.lbl_state.pack(fill="x", padx=10, pady=(0, 8))

        search = ttk.Frame(self)
        search.pack(fill="x", padx=10)
        ttk.Label(search, text=i18n.t("mime.search", "Rechercher") + " :").pack(side="left")
        self.var_query = tk.StringVar()
        entry = ttk.Entry(search, textvariable=self.var_query, width=40)
        entry.pack(side="left", padx=6)
        entry.bind("<Return>", lambda _e: self._search())
        make_button(search, i18n.t("mime.search_btn", "Chercher"), self._search).pack(side="left")

        holder = ttk.Frame(self)
        holder.pack(fill="both", expand=True, padx=10, pady=8)
        self.tree = ttk.Treeview(holder, columns=("name", "label", "state"),
                                 show="headings", height=16)
        for col, titre, largeur in (
                ("name", i18n.t("mime.col_name", "Type"), 380),
                ("label", i18n.t("mime.col_label", "Description"), 340),
                ("state", i18n.t("mime.col_state", "État"), 120)):
            self.tree.heading(col, text=titre)
            self.tree.column(col, width=largeur, anchor="w")
        vsb = ttk.Scrollbar(holder, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=vsb.set)
        self.tree.pack(side="left", fill="both", expand=True)
        vsb.pack(side="right", fill="y")
        for etat, couleur in MIME_STATUS_COLORS.items():
            self.tree.tag_configure(etat, foreground=couleur)

        self._refresh_state()

    # -- état ---------------------------------------------------------------
    def _refresh_state(self):
        """Compteurs **et provenance** : intégré à l'exe, ou fichier importé ?

        Les deux situations se ressemblent à l'écran et ne se corrigent pas de
        la même façon — c'est la première chose à vérifier quand un libellé
        manque ou surprend.
        """
        st = mime_catalog.stats()
        if not st["descriptions"]:
            texte = i18n.t(
                "mime.state_empty",
                "Aucun référentiel chargé. Les filtres restent lisibles, mais sans "
                "description. Importez le fichier depuis votre installation d'Intella.")
            couleur = "#b91c1c"
        else:
            texte = i18n.t(
                "mime.state",
                "{d} descriptions (dont {c} catégories) — {o} nom(s) observé(s) dans "
                "vos cas, dont {s} sans description.",
                d=st["descriptions"], c=st["categories"], o=st["observed"],
                s=st["observed_only"])
            if st["external"]:
                couleur = "#1d4ed8"
                texte += "\n" + i18n.t(
                    "mime.origin_external",
                    "Source : FICHIER EXTERNE, qui remplace la version intégrée "
                    "({e} descriptions).", e=st["embedded_descriptions"])
                texte += "\n" + i18n.t("mime.state_file", "Fichier : {f}",
                                       f=st["source"])
            else:
                couleur = "#166534"
                texte += "\n" + i18n.t(
                    "mime.origin_embedded",
                    "Source : version INTÉGRÉE à l'application. Déposer un fichier "
                    ".properties dans le dossier ci-dessous la remplacerait.")
            if st["observed_learned"]:
                texte += "\n" + i18n.t(
                    "mime.origin_learned",
                    "{n} nom(s) appris de vos cas s'ajoutent à ceux livrés.",
                    n=st["observed_learned"])
            if st["duplicates"]:
                texte += "\n" + i18n.t(
                    "mime.state_duplicates",
                    "{n} clé(s) en double dans le fichier — la dernière valeur "
                    "l'emporte.", n=st["duplicates"])
        self.lbl_state.config(text=texte, foreground=couleur)

    # -- actions ------------------------------------------------------------
    def _import(self):
        titre = i18n.t("mime.import_title", "Importer un référentiel de types MIME")
        chemin = filedialog.askopenfilename(
            title=titre,
            filetypes=[(i18n.t("mime.filetype", "Descriptions Intella"), "*.properties"),
                       (i18n.t("common.filetype_all", "Tous"), "*.*")])
        if not chemin:
            return
        try:
            bilan = mime_catalog.import_descriptions(chemin)
        except ValueError as exc:
            messagebox.showerror(titre, str(exc))
            return
        self._refresh_state()
        msg = i18n.t("mime.import_ok", "{n} description(s) importée(s).",
                     n=bilan["count"])
        if bilan["added"]:
            msg += "\n" + i18n.t("mime.import_added", "{n} nouveau(x) type(s).",
                                 n=len(bilan["added"]))
        if bilan["removed"]:
            # Une perte se dit : des filtres jusque-là lisibles ne le seront plus.
            msg += "\n" + i18n.t(
                "mime.import_removed",
                "⚠ {n} type(s) décrit(s) par l'ancien fichier ne le sont plus : {ex}…",
                n=len(bilan["removed"]), ex=", ".join(bilan["removed"][:3]))
        if bilan["duplicates"]:
            msg += "\n" + i18n.t("mime.import_duplicates",
                                 "{n} clé(s) en double dans le fichier.",
                                 n=len(bilan["duplicates"]))
        self.app.log.log(msg.replace("\n", " "))
        messagebox.showinfo(titre, msg)

    def _learn_xml(self):
        """Récolte les noms de types d'un export ``-exportSourceList``.

        La liste livrée avec l'application vient d'une manipulation qu'on ne
        refait pas par hasard (cocher méthodiquement l'interface d'Intella pour
        que le XML contienne le complément). C'est ici qu'on la complète quand
        Intella change de version : refaire la manipulation, exporter, importer.
        """
        titre = i18n.t("mime.learn_title", "Apprendre des types depuis un export")
        chemin = filedialog.askopenfilename(
            title=titre,
            filetypes=[(i18n.t("mime.filetype_xml", "Export de sources Intella"), "*.xml"),
                       (i18n.t("common.filetype_all", "Tous"), "*.*")])
        if not chemin:
            return
        try:
            nouveaux = mime_catalog.learn_from_xml(chemin)
        except ValueError as exc:
            messagebox.showerror(titre, str(exc))
            return
        self._refresh_state()
        msg = (i18n.t("mime.learn_ok", "{n} nouveau(x) type(s) appris.", n=len(nouveaux))
               if nouveaux else
               i18n.t("mime.learn_none", "Aucun type nouveau : ils étaient déjà connus."))
        self.app.log.log(msg)
        messagebox.showinfo(titre, msg)

    def _search(self):
        motif = self.var_query.get().strip().lower()
        self.tree.delete(*self.tree.get_children())
        resultats = mime_catalog.search(motif, limit=500)
        for nom, etat, libelle in resultats:
            self.tree.insert("", "end",
                             values=(nom or i18n.t("mime.untyped", "(sans type)"),
                                     libelle, mime_status_label(etat)),
                             tags=(etat,))
        if not resultats:
            self.app.log.log(i18n.t("mime.search_none",
                                    "Aucun type ne correspond à « {q} ».",
                                    q=self.var_query.get().strip()))


class FilesTab(ttk.Frame):
    """Où l'application range ses fichiers, et quelle version tourne.

    Utile au dépannage : l'exe est distribué à la main, et savoir *quel* `.ini`
    est lu évite d'éditer le mauvais (il tombe dans ``%APPDATA%`` quand le
    dossier de l'exe n'est pas inscriptible).
    """

    def __init__(self, parent, app):
        super().__init__(parent)
        self.app = app

        ttk.Label(self, font=("Segoe UI", 10, "bold"),
                  text=f"{config.APP_TITLE} v{config.APP_VERSION}").pack(
            anchor="w", padx=10, pady=(10, 8))

        for cle, defaut, chemin in (
                ("files.base", "Dossier de l'application", config.base_dir()),
                ("files.ini", "Paramètres (.ini)", app.settings.path),
                ("files.profiles", "Profils d'analyse", config.profiles_dir()),
                ("files.lang", "Langues", config.lang_dir()),
                ("files.mime", "Référentiel de types MIME", config.mime_dir())):
            self._row(i18n.t(cle, defaut), chemin)

    def _row(self, libelle, chemin):
        ligne = ttk.Frame(self)
        ligne.pack(fill="x", padx=10, pady=2)
        ttk.Label(ligne, text=libelle + " :", width=28).pack(side="left")
        etat = "" if os.path.exists(chemin) else "  " + i18n.t("files.missing", "(absent)")
        ttk.Label(ligne, text=chemin + etat).pack(side="left")
        make_button(ligne, i18n.t("files.open", "Ouvrir"),
                    lambda c=chemin: open_folder(c)).pack(side="right")


# --- Utilitaires partagés --------------------------------------------------

def open_folder(chemin: str) -> None:
    """Ouvre un dossier dans l'Explorateur (le crée s'il manque).

    Sans création, « Ouvrir » ne ferait rien du tout sur un référentiel jamais
    importé — et l'utilisateur ne saurait pas où déposer son fichier.
    """
    try:
        cible = chemin if os.path.isdir(chemin) else os.path.dirname(chemin)
        os.makedirs(cible, exist_ok=True)
        subprocess.Popen(["explorer", os.path.normpath(cible)])
    except OSError:
        pass
