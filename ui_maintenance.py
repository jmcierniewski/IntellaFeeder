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
from tkinter import filedialog, messagebox, simpledialog, ttk

import config
import i18n
import mime_catalog
import ui_theme
from ui_journal import JournalTab
from ui_widgets import (MIME_STATUS_COLORS, attach_tip, make_button,
                        mime_status_label)


class MaintenanceTab(ttk.Frame):
    def __init__(self, parent, app):
        super().__init__(parent)
        self.app = app

        nb = ttk.Notebook(self, style="Sub.TNotebook")
        self.notebook = nb
        nb.pack(fill="both", expand=True, padx=0, pady=0)

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

    LECTURE = 780          # largeur de lecture plafonnée des explications

    def __init__(self, parent, app):
        super().__init__(parent)
        self.app = app

        page = ttk.Frame(self)
        page.pack(fill="both", expand=True, padx=app.theme.pad, pady=app.theme.pad)

        # --- Affichage (décision D9, 11/09/2026) -------------------------- #
        # Le poste va du portable 13 pouces au 22 pouces : plutôt que de choisir
        # une densité moyenne qui ne convient nulle part, on la rend réglable.
        # Le changement est IMMÉDIAT (polices Tk nommées, cf. ui_theme) — une
        # option d'affichage qui exigerait un redémarrage ne serait pas essayée.
        box = ttk.LabelFrame(page, text=i18n.t("options.display", "Affichage"))
        box.pack(fill="x", pady=(0, app.theme.gap))

        ligne = ttk.Frame(box)
        ligne.pack(fill="x", padx=8, pady=(8, 4))
        ttk.Label(ligne, text=i18n.t("options.language", "Langue"),
                  width=22).pack(side="left")
        # Repli explicite : un code vide (ou disparu des langues disponibles)
        # laisserait le champ vide, ce qui se lit comme « aucune langue ».
        codes = i18n.available_languages()
        courant = i18n.current_code()
        if courant not in codes:
            courant = i18n.BASE_LANGUAGE if i18n.BASE_LANGUAGE in codes else (
                codes[0] if codes else i18n.BASE_LANGUAGE)
        self.var_lang = tk.StringVar(value=courant)
        cb = ttk.Combobox(ligne, textvariable=self.var_lang, state="readonly",
                          width=8, values=codes)
        cb.pack(side="left")
        cb.bind("<<ComboboxSelected>>",
                lambda _e: self.app.change_language(self.var_lang.get()))
        ttk.Label(ligne, style="Hint.TLabel", text=i18n.t(
            "options.language_hint", "appliquée au redémarrage")).pack(side="left", padx=8)

        ligne = ttk.Frame(box)
        ligne.pack(fill="x", padx=8, pady=4)
        ttk.Label(ligne, text=i18n.t("options.density", "Densité d'affichage"),
                  width=22).pack(side="left")
        self.var_density = tk.StringVar(value=app.theme.density)
        self._density_btns = {}
        for d in ui_theme.DENSITIES:
            b = make_button(ligne, ui_theme.density_label(d),
                            lambda dd=d: self._set_density(dd))
            b.pack(side="left", padx=(0, 4))
            self._density_btns[d] = b

        ligne = ttk.Frame(box)
        ligne.pack(fill="x", padx=8, pady=4)
        ttk.Label(ligne, text=i18n.t("options.font_scale", "Taille du texte"),
                  width=22).pack(side="left")
        make_button(ligne, "A−", lambda: self._bump_scale(-ui_theme.SCALE_STEP),
                    width=3).pack(side="left")
        self.lbl_scale = ttk.Label(ligne, text="100 %", width=7, anchor="center")
        self.lbl_scale.pack(side="left", padx=4)
        make_button(ligne, "A+", lambda: self._bump_scale(ui_theme.SCALE_STEP),
                    width=3).pack(side="left")
        make_button(ligne, i18n.t("options.scale_reset", "Rétablir"),
                    lambda: self._set_scale(100)).pack(side="left", padx=8)

        ttk.Label(box, wraplength=self.LECTURE, justify="left", style="Hint.TLabel",
                  text=i18n.t(
                      "options.density_help",
                      "La densité agit sur la hauteur des lignes des tableaux et sur "
                      "les marges : « compacte » pour voir davantage de sources sur un "
                      "écran de portable, « confortable » sur un grand écran. Les deux "
                      "réglages s'appliquent immédiatement.")).pack(
            anchor="w", padx=8, pady=(2, 8))

        # --- Import de sources -------------------------------------------- #
        box = ttk.LabelFrame(page, text=i18n.t("options.import", "Import de sources"))
        box.pack(fill="x", pady=(0, app.theme.gap))

        self.var_recursive = tk.BooleanVar(
            value=app.settings.get("recursive_default", "0").strip()
            in ("1", "true", "oui", "vrai"))
        ttk.Checkbutton(
            box, variable=self.var_recursive,
            command=self._save_recursive,
            text=i18n.t("options.recursive_default",
                        "Explorer les sous-dossiers par défaut (dépôt d'images "
                        "forensiques)")).pack(anchor="w", padx=8, pady=(8, 2))
        ttk.Label(box, wraplength=self.LECTURE, justify="left", style="Hint.TLabel",
                  text=i18n.t(
                      "options.recursive_help",
                      "Décoché, un dossier déposé n'est exploré qu'au premier niveau : "
                      "un dossier de scellés voisine souvent avec d'autres cas ou des "
                      "copies de travail, et descendre d'office ramènerait des images "
                      "étrangères. Coché si vos images sont systématiquement rangées "
                      "dans des sous-dossiers. La case reste modifiable à chaque dépôt "
                      "dans l'onglet Import.")).pack(anchor="w", padx=8, pady=(0, 8))

        # --- Glisser-déposer ---------------------------------------------- #
        # L'interrupteur de secours n'existait qu'au `.ini` : un poste qui
        # s'accommoderait mal du dépôt devait être dépanné à l'éditeur de texte.
        box = ttk.LabelFrame(page, text=i18n.t("options.dnd", "Glisser-déposer"))
        box.pack(fill="x")
        self.var_dnd = tk.BooleanVar(
            value=app.settings.get("enable_dnd", "1").strip()
            not in ("0", "false", "non", "faux"))
        ttk.Checkbutton(
            box, variable=self.var_dnd, command=self._save_dnd,
            text=i18n.t("options.dnd_enable",
                        "Activer le glisser-déposer depuis l'Explorateur")).pack(
            anchor="w", padx=8, pady=(8, 2))
        ttk.Label(box, wraplength=self.LECTURE, justify="left", style="Hint.TLabel",
                  text=i18n.t(
                      "options.dnd_help",
                      "Interrupteur de secours : décoché, l'application reste "
                      "utilisable par le collage de chemins et les boutons "
                      "« Ajouter… ». Le changement prend effet au redémarrage.")).pack(
            anchor="w", padx=8, pady=(0, 8))

        self._refresh_display_state()

    # -- affichage ------------------------------------------------------- #
    def _set_density(self, densite):
        self.app.theme.set_density(densite)
        self.app.settings.set("density", densite)
        self.app.settings.save()
        self._refresh_display_state()

    def _bump_scale(self, delta):
        self._set_scale(self.app.theme.scale + delta)

    def _set_scale(self, valeur):
        self.app.theme.set_scale(valeur)
        self.app.settings.set("font_scale", str(self.app.theme.scale))
        self.app.settings.save()
        self._refresh_display_state()

    def _refresh_display_state(self):
        """Montre la densité active : trois boutons identiques n'en disent rien."""
        for d, b in self._density_btns.items():
            actif = (d == self.app.theme.density)
            b.configure(bg=config.ACCENT if actif else config.UI_SURFACE,
                        fg="white" if actif else config.UI_INK,
                        highlightbackground=config.ACCENT if actif else "#9fadba")
        self.lbl_scale.configure(text=f"{self.app.theme.scale} %")

    def _save_dnd(self):
        self.app.settings.set("enable_dnd", "1" if self.var_dnd.get() else "0")
        self.app.settings.save()
        self.app.log.log(i18n.t(
            "options.dnd_saved", "Glisser-déposer : {v} (au prochain démarrage).",
            v=i18n.t("common.yes", "oui") if self.var_dnd.get()
            else i18n.t("common.no", "non")))

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
    """Référentiel des types MIME : voir l'ensemble, chercher, enrichir.

    **La liste s'affiche ENTIÈRE au chargement** (11/09/2026). Elle partait vide
    et n'apparaissait qu'après une recherche : impossible de répondre à « qu'y
    a-t-il là-dedans ? », ni de vérifier qu'un import avait servi à quelque
    chose. La colonne « Vient de » répond à l'autre moitié de la question —
    socle intégré, fichier importé, ou votre propre description.
    """

    # ⚠ Les libellés se lisent à l'AFFICHAGE, pas au chargement du module : une
    # constante de classe figerait la langue du premier import, et la colonne
    # « Comes from » restait en français en US (constaté le 11/09/2026).
    ORIGINES_COULEURS = {
        "embedded": config.UI_INK_2,
        "external": "#1d4ed8",
        "user": "#0f766e",
    }

    @staticmethod
    def origine_libelle(origine: str) -> str:
        return {
            "embedded": i18n.t("mime.origin_embedded_short", "intégré"),
            "external": i18n.t("mime.origin_external_short", "fichier importé"),
            "user": i18n.t("mime.origin_user_short", "vous"),
        }.get(origine, "—")

    def __init__(self, parent, app):
        super().__init__(parent)
        self.app = app
        pad = app.theme.pad
        self._filtre = "all"

        ttk.Label(self, wraplength=980, justify="left", style="Hint.TLabel", text=i18n.t(
            "mime.intro",
            "Les filtres de types d'une source sont des listes de noms techniques "
            "— souvent plusieurs centaines. Le fichier de descriptions livré avec "
            "Intella (mimetype-descriptions_<langue>.properties, dans son dossier "
            "d'installation) permet de les afficher en clair.")).pack(
            fill="x", padx=pad, pady=(pad, 4))

        bar = ttk.Frame(self)
        bar.pack(fill="x", padx=pad, pady=(0, 4))
        b = make_button(bar, i18n.t("mime.import", "Importer un fichier de descriptions…"),
                        self._import)
        b.pack(side="left")
        attach_tip(b, i18n.t(
            "mime.import_tip",
            "Ajoute les libellés d'un .properties d'Intella à ceux déjà connus.\n"
            "Les entrées de même nom sont remplacées par celles du fichier ; "
            "les autres restent en place. Rien n'est perdu : plusieurs imports "
            "successifs s'additionnent dans un fichier unique."))
        b = make_button(bar, i18n.t("mime.learn_xml", "Apprendre depuis un export XML…"),
                        self._learn_xml)
        b.pack(side="left", padx=6)
        attach_tip(b, i18n.t(
            "mime.learn_tip",
            "Récolte les NOMS de types présents dans un export de sources, sans "
            "leur donner de libellé.\n\nÀ quoi ça sert : Intella écrit dans ses "
            "filtres des synonymes qu'il ne décrit nulle part (18 % d'un filtre "
            "réel). Les apprendre évite qu'ils s'affichent « inconnus » — ce qui "
            "ferait passer pour une anomalie ce qui est normal."))
        make_button(bar, i18n.t("mime.open_folder", "Ouvrir le dossier"),
                    lambda: open_folder(config.mime_dir())).pack(side="left")

        self.lbl_state = ttk.Label(self, justify="left", style="Hint.TLabel")
        self.lbl_state.pack(fill="x", padx=pad, pady=(0, 6))

        search = ttk.Frame(self)
        search.pack(fill="x", padx=pad)
        ttk.Label(search, text=i18n.t("mime.search", "Rechercher") + " :").pack(side="left")
        self.var_query = tk.StringVar()
        entry = ttk.Entry(search, textvariable=self.var_query, width=34)
        entry.pack(side="left", padx=6)
        entry.bind("<KeyRelease>", lambda _e: self._refresh_list())
        ttk.Separator(search, orient="vertical").pack(side="left", fill="y", padx=8)
        self._btn_filtres = {}
        for cle, libelle in (
                ("all", i18n.t("mime.filter_all", "Tous")),
                ("undescribed", i18n.t("mime.filter_undescribed", "Sans description")),
                ("user", i18n.t("mime.filter_user", "Décrits par vous")),
                ("external", i18n.t("mime.filter_external", "Venus d'un import"))):
            b = make_button(search, libelle, lambda c=cle: self._set_filtre(c))
            b.pack(side="left", padx=(0, 4))
            self._btn_filtres[cle] = b
        make_button(search, i18n.t("mime.describe", "Décrire ce type…"),
                    self._decrire).pack(side="right")

        holder = ttk.Frame(self)
        holder.pack(fill="both", expand=True, padx=pad, pady=8)
        self.tree = ttk.Treeview(holder, columns=("name", "label", "state", "origin"),
                                 show="headings")
        for col, titre, largeur in (
                ("name", i18n.t("mime.col_name", "Type"), 340),
                ("label", i18n.t("mime.col_label", "Description"), 320),
                ("state", i18n.t("mime.col_state", "État"), 130),
                ("origin", i18n.t("mime.col_origin", "Vient de"), 130)):
            self.tree.heading(col, text=titre)
            self.tree.column(col, width=largeur, anchor="w")
        vsb = ttk.Scrollbar(holder, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=vsb.set)
        self.tree.pack(side="left", fill="both", expand=True)
        vsb.pack(side="right", fill="y")
        for etat, couleur in MIME_STATUS_COLORS.items():
            self.tree.tag_configure(etat, foreground=couleur)
        self.tree.bind("<Double-1>", lambda _e: self._decrire())
        # C'est ICI qu'on nomme un type : le sous-onglet Profils l'a proposé une
        # journée, puis y a renoncé (un seul point d'entrée pour l'entretien du
        # référentiel). D'où l'infobulle des états, qui n'y était pas.
        attach_tip(self.tree, i18n.t(
            "mime.states_tip",
            "État d'un type dans le référentiel :\n"
            "• décrit — libellé fourni par Vound ;\n"
            "• décrit par vous — libellé que vous avez saisi ;\n"
            "• connu, sans libellé — le nom existe (Intella l'écrit), mais "
            "personne ne le décrit. C'est un synonyme valide, il n'y a rien à "
            "corriger ;\n"
            "• inconnu — jamais rencontré. Vérifiez l'orthographe, ou votre "
            "version d'Intella est plus récente que le référentiel."))

        self.lbl_count = ttk.Label(self, style="Hint.TLabel")
        self.lbl_count.pack(anchor="w", padx=pad, pady=(0, pad))

        self._refresh_state()
        self._refresh_list()

    # -- état ---------------------------------------------------------------
    def _refresh_state(self):
        """Compteurs et **provenance** : intégré seul, ou enrichi par des imports ?"""
        st = mime_catalog.stats()
        if not st["descriptions"]:
            texte = i18n.t(
                "mime.state_empty",
                "Aucun référentiel chargé. Les filtres restent lisibles, mais sans "
                "description. Importez le fichier depuis votre installation d'Intella.")
            couleur = config.DANGER_COLOR
        else:
            texte = i18n.t(
                "mime.state",
                "{d} descriptions (dont {c} catégories) — {o} nom(s) de type "
                "connu(s), dont {s} sans description.",
                d=st["descriptions"], c=st["categories"], o=st["observed"],
                s=st["observed_only"])
            if st["external"]:
                couleur = "#1d4ed8"
                texte += "  " + i18n.t(
                    "mime.origin_merged",
                    "{n} description(s) viennent de {f} fichier(s) importé(s), "
                    "ajoutées aux {e} intégrées.",
                    n=st["external_count"], f=st["external_files"],
                    e=st["embedded_descriptions"])
            else:
                couleur = "#166534"
                texte += "  " + i18n.t(
                    "mime.origin_embedded",
                    "Toutes viennent de la version intégrée à l'application ; "
                    "importer un .properties d'Intella y ajouterait les siennes.")
            if st["duplicates"]:
                texte += "  " + i18n.t(
                    "mime.state_duplicates",
                    "{n} clé(s) en double dans le fichier — la dernière valeur "
                    "l'emporte.", n=st["duplicates"])
        self.lbl_state.config(text=texte, foreground=couleur)

    # -- liste --------------------------------------------------------------
    def _set_filtre(self, cle):
        self._filtre = cle
        self._refresh_list()

    def _refresh_list(self):
        motif = self.var_query.get().strip().lower()
        self.tree.delete(*self.tree.get_children())
        lignes = mime_catalog.search(motif, limit=5000)
        montrees = 0
        for nom, etat, _describe in lignes:
            # ⚠ `search` rend `describe()`, qui retombe sur le NOM quand il n'y a
            # pas de libellé : afficher ça remplirait la colonne « Description »
            # d'une copie du type, et « Sans description » ne filtrerait plus
            # rien. `label()` rend None — c'est lui qu'il faut ici.
            libelle = mime_catalog.label(nom) or ""
            origine = mime_catalog.origin(nom)
            if self._filtre == "undescribed" and libelle:
                continue
            if self._filtre == "user" and origine != "user":
                continue
            if self._filtre == "external" and origine != "external":
                continue
            titre = self.origine_libelle(origine)
            self.tree.insert("", "end", tags=(etat,),
                             values=(nom or i18n.t("mime.untyped", "(sans type)"),
                                     libelle, mime_status_label(etat), titre))
            montrees += 1
        self.lbl_count.config(text=i18n.t("mime.shown", "{n} type(s) affiché(s).",
                                          n=montrees))
        for cle, bouton in self._btn_filtres.items():
            actif = (cle == self._filtre)
            bouton.configure(bg=config.ACCENT if actif else config.UI_SURFACE,
                             fg="white" if actif else config.UI_INK,
                             highlightbackground=config.ACCENT if actif else "#9fadba")

    def _selection(self) -> str | None:
        sel = self.tree.selection()
        if not sel:
            return None
        nom = self.tree.item(sel[0], "values")[0]
        vide = i18n.t("mime.untyped", "(sans type)")
        return "" if nom == vide else nom

    def _decrire(self):
        nom = self._selection()
        if nom is None:
            messagebox.showinfo(i18n.t("mime.describe_title", "Décrire un type"),
                                i18n.t("mime.describe_none",
                                       "Sélectionnez d'abord un type dans la liste."))
            return
        titre = i18n.t("mime.describe_title", "Décrire un type")
        texte = simpledialog.askstring(
            titre, i18n.t("mime.describe_prompt", "Votre description pour « {t} » :",
                          t=nom or "(sans type)"),
            initialvalue=mime_catalog.user_label(nom) or "", parent=self)
        if texte is None:
            return
        mime_catalog.set_user_label(nom, texte)
        self._refresh_state()
        self._refresh_list()
        self.app.log.log(i18n.t("mime.describe_log",
                                "Description personnelle : {t} → « {d} »",
                                t=nom or "(sans type)", d=texte.strip()))

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
        self._refresh_list()
        msg = i18n.t("mime.import_ok",
                     "{n} description(s) lue(s) dans le fichier.", n=bilan["count"])
        msg += "\n" + i18n.t("mime.import_added", "{n} type(s) gagnent un libellé.",
                             n=len(bilan["added"]))
        if bilan["updated"]:
            msg += "\n" + i18n.t("mime.import_updated",
                                 "{n} libellé(s) remplacé(s) par celui du fichier.",
                                 n=len(bilan["updated"]))
        if bilan["kept"]:
            msg += "\n" + i18n.t("mime.import_kept",
                                 "{n} étaient déjà identiques.", n=bilan["kept"])
        msg += "\n\n" + i18n.t("mime.import_total",
                               "Le référentiel compte maintenant {n} descriptions.",
                               n=bilan["total"])
        if bilan["duplicates"]:
            msg += "\n" + i18n.t("mime.import_duplicates",
                                 "{n} clé(s) en double dans le fichier.",
                                 n=len(bilan["duplicates"]))
        self.app.log.log(msg.replace("\n", " "))
        messagebox.showinfo(titre, msg)

    def _learn_xml(self):
        """Récolte les noms de types d'un export ``-exportSourceList``."""
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
        self._refresh_list()
        msg = (i18n.t("mime.learn_ok", "{n} nouveau(x) type(s) appris.", n=len(nouveaux))
               if nouveaux else
               i18n.t("mime.learn_none", "Aucun type nouveau : ils étaient déjà connus."))
        self.app.log.log(msg)
        messagebox.showinfo(titre, msg)


class FilesTab(ttk.Frame):
    """Où l'application range ses fichiers, et quelle version tourne.

    Écran de **diagnostic** (refait le 11/09/2026 : il était « moche »). Un
    tableau plutôt que cinq lignes flottantes, et une colonne « État » qui dit
    ce qu'il y a dans chaque dossier — c'est la première chose qu'on veut savoir
    quand un profil ou une langue n'apparaît pas.
    """

    def __init__(self, parent, app):
        super().__init__(parent)
        self.app = app
        pad = app.theme.pad

        entete = ttk.Frame(self)
        entete.pack(fill="x", padx=pad, pady=(pad, 6))
        ttk.Label(entete, font=ui_theme.F_TITLE,
                  text=f"{config.APP_NAME} v{config.APP_VERSION}").pack(side="left")
        ttk.Label(entete, style="Hint.TLabel",
                  text="  " + i18n.t("app.subtitle",
                                     "Générateur de sources d'import Intella")).pack(
            side="left")
        make_button(entete, i18n.t("files.copy", "Copier ces informations"),
                    self._copier).pack(side="right")

        holder = ttk.Frame(self)
        holder.pack(fill="both", expand=True, padx=pad, pady=(0, 6))
        self.tree = ttk.Treeview(holder, columns=("what", "where", "state"),
                                 show="headings", height=8)
        for col, titre, largeur in (
                ("what", i18n.t("files.col_what", "Élément"), 220),
                ("where", i18n.t("files.col_where", "Emplacement"), 520),
                ("state", i18n.t("files.col_state", "État"), 230)):
            self.tree.heading(col, text=titre)
            self.tree.column(col, width=largeur, anchor="w")
        vsb = ttk.Scrollbar(holder, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=vsb.set)
        self.tree.pack(side="left", fill="both", expand=True)
        vsb.pack(side="right", fill="y")
        self.tree.tag_configure("manquant", foreground=config.WARN_COLOR)
        self.tree.bind("<Double-1>", lambda _e: self._ouvrir())

        pied = ttk.Frame(self)
        pied.pack(fill="x", padx=pad, pady=(0, pad))
        make_button(pied, i18n.t("files.open", "Ouvrir"), self._ouvrir).pack(side="left")
        # Le dossier `lang\` déroutait : réclamé par cet écran, jamais créé, et
        # vide quand on le créait à la main — parce que les langues sont
        # EMBARQUÉES et qu'il ne sert qu'à en corriger une sans reconstruire
        # l'exe. Ce bouton lui donne enfin un contenu de départ.
        btn = make_button(pied, i18n.t("files.write_lang", "Écrire les langues ici…"),
                          self._ecrire_langues)
        btn.pack(side="left", padx=6)
        attach_tip(btn, i18n.t(
            "files.write_lang_tip",
            "Dépose dans le dossier « lang » une copie des langues intégrées à "
            "l'application (FR, US).\n\n"
            "À quoi ça sert : un fichier .lang présent l'emporte sur la version "
            "intégrée. C'est le moyen de corriger une traduction, ou d'ajouter "
            "une langue, sans reconstruire l'exécutable. Le dossier reste "
            "FACULTATIF : sans lui, l'application tourne déjà en FR et en US."))
        ttk.Label(pied, style="Hint.TLabel", text=i18n.t(
            "files.hint",
            "Double-cliquez une ligne pour l'ouvrir. Un dossier absent n'est pas "
            "une anomalie : il est créé au premier usage.")).pack(side="left", padx=10)

        self._remplir()

    def _remplir(self):
        self._chemins = []
        for cle, defaut, chemin, etat in self._lignes():
            self._chemins.append(chemin)
            existe = os.path.exists(chemin)
            self.tree.insert("", "end", values=(
                i18n.t(cle, defaut), chemin,
                etat if existe else i18n.t("files.missing", "absent")),
                tags=() if existe else ("manquant",))

    def _lignes(self):
        def compter(dossier, suffixe):
            try:
                return sum(1 for f in os.listdir(dossier) if f.lower().endswith(suffixe))
            except OSError:
                return 0

        prof = config.profiles_dir()
        lang = config.lang_dir()
        mime = config.mime_dir()
        cas = os.path.join(config.base_dir(), config.CAS_DIRNAME)
        return [
            ("files.base", "Dossier de l'application", config.base_dir(), ""),
            ("files.ini", "Paramètres (.ini)", self.app.settings.path,
             i18n.t("files.state_ok", "lu au démarrage")),
            ("files.profiles", "Profils d'analyse", prof,
             i18n.t("files.n_files", "{n} fichier(s)", n=compter(prof, ".json"))),
            # ⚠ Dossier FACULTATIF : les langues sont embarquées à l'exe
            # (`lang_data.py`). L'écran disait « absent » en orange, comme
            # d'un manque — alors qu'il n'y a rien à réparer.
            ("files.lang", "Langues (dossier facultatif)", lang,
             i18n.t("files.lang_state",
                    "{l} — intégrées à l'application ; {n} fichier(s) ici",
                    l=", ".join(i18n.available_languages()),
                    n=compter(lang, ".lang"))),
            ("files.mime", "Référentiel de types MIME", mime,
             i18n.t("files.n_files", "{n} fichier(s)", n=compter(mime, ".properties"))),
            ("files.cases", "Sorties générées", cas,
             i18n.t("files.n_cases", "{n} cas", n=len(_sous_dossiers(cas)))),
        ]

    def _ecrire_langues(self):
        """Dépose les langues intégrées dans ``lang\\`` — le dossier devient utile.

        On n'écrase JAMAIS un fichier déjà là : il porte peut-être une
        traduction corrigée à la main, et c'est précisément l'usage du dossier.
        """
        import json
        import lang_data
        dossier = config.lang_dir()
        titre = i18n.t("files.write_lang", "Écrire les langues ici…")
        ecrits, gardes = [], []
        try:
            os.makedirs(dossier, exist_ok=True)
            for code, contenu in sorted(lang_data.BUILTIN.items()):
                chemin = os.path.join(dossier, "%s.lang" % code)
                if os.path.exists(chemin):
                    gardes.append(code)
                    continue
                with open(chemin, "w", encoding="utf-8", newline="\n") as fh:
                    json.dump(contenu, fh, ensure_ascii=False, indent=4)
                    fh.write("\n")
                ecrits.append(code)
        except OSError as exc:
            messagebox.showerror(titre, str(exc))
            return
        self._remplir()
        message = i18n.t("files.write_lang_done",
                         "{n} fichier(s) écrit(s) dans {d}.",
                         n=len(ecrits), d=dossier)
        if gardes:
            message += "\n" + i18n.t(
                "files.write_lang_kept",
                "Déjà présent(s), laissé(s) intact(s) : {l}.", l=", ".join(gardes))
        messagebox.showinfo(titre, message)
        self.app.log.log(message.replace("\n", " "))

    def _ouvrir(self):
        sel = self.tree.selection()
        if not sel:
            return
        index = self.tree.index(sel[0])
        if 0 <= index < len(self._chemins):
            open_target(self._chemins[index])

    def _copier(self):
        """De quoi coller un état complet dans un message de dépannage."""
        lignes = [f"{config.APP_NAME} v{config.APP_VERSION}"]
        for cle, defaut, chemin, etat in self._lignes():
            present = "" if os.path.exists(chemin) else "  (absent)"
            lignes.append(f"{i18n.t(cle, defaut)} : {chemin}{present}  {etat}".rstrip())
        texte = "\n".join(lignes)
        try:
            self.clipboard_clear()
            self.clipboard_append(texte)
        except tk.TclError:
            return
        self.app.log.log(i18n.t("files.copied", "Informations de version copiées."))


def _sous_dossiers(chemin: str) -> list:
    try:
        return [d for d in os.listdir(chemin)
                if os.path.isdir(os.path.join(chemin, d))]
    except OSError:
        return []


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


def open_target(chemin: str) -> None:
    """Ouvre un FICHIER avec son application par défaut ; un dossier sinon.

    Corrigé le 10/09/2026 : « Ouvrir » ouvrait le dossier parent même quand la
    ligne désignait un fichier (`intellafeeder.ini`). Il fallait ensuite le
    retrouver à l'œil dans le dossier — alors que le bouton est en face de son
    chemin. Un dossier, lui, s'ouvre toujours dans l'Explorateur.
    """
    try:
        if os.path.isfile(chemin):
            os.startfile(os.path.normpath(chemin))   # noqa: S606 (Windows only)
            return
    except OSError:
        # Pas d'association pour cette extension (un .ini sans éditeur associé,
        # par exemple) : on retombe sur le dossier, qui vaut mieux que rien.
        pass
    open_folder(chemin)
