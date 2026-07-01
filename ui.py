"""Fenêtre principale à onglets (Import / Export des sources / Journal)."""

import os
import tkinter as tk
from tkinter import filedialog, messagebox, ttk

import config
import i18n
import path_parser
from app_log import AppLog
from settings import Settings
from ui_detail import DetailTab
from ui_export import ExportTab
from ui_help import HelpTab
from ui_import import ImportTab
from ui_journal import JournalTab
from ui_profiles import ProfilesTab
from ui_widgets import make_button


class MainWindow:
    """Assemble la barre commune (utilisateur + IntellaCmd) et le Notebook."""

    def __init__(self, root: tk.Tk):
        self.root = root
        self.settings = Settings()
        self.log = AppLog()
        # Métadonnées du cas (case.xml/prefs/tasks2) publiées par l'Inventaire.
        self.case_meta = None
        # Liste des sources déjà indexées (export -exportSourceList), pour le dédoublonnage.
        self.inventory = None

        # Langue de l'interface : chargée AVANT toute construction de widget pour
        # que tous les i18n.t() reflètent le bon choix dès le premier affichage.
        # Changer la langue en cours de session (dropdown) ne retraduit pas les
        # widgets déjà construits : le nouveau choix s'applique au redémarrage.
        self._init_language()

        # Variables partagées entre onglets.
        # Utilisateur : LECTURE SEULE, issu de case.xml (rempli à la détection).
        self.var_user = tk.StringVar(value=self.settings.get("user"))
        self.var_exe = tk.StringVar(value=self.settings.get("intellacmd_path"))
        # IntellaCmd.exe verrouillé en GUI s'il est déjà mémorisé dans le .ini.
        self._exe_locked = bool(self.settings.get("intellacmd_path").strip())

        root.title(f"{i18n.t('app.title', config.APP_TITLE)} v{config.APP_VERSION}")
        # Onglet Import dense (barre commune + langue + 5 lignes de paramètres +
        # 2 lignes de toolbar) : 1060x840 masquait les boutons du bas sur des
        # écrans standards. Fenêtre maximisée par défaut (s'adapte à tout écran) ;
        # geometry/minsize ci-dessous servent de taille si l'utilisateur restaure.
        root.geometry("1200x900")
        root.minsize(1000, 800)
        try:
            root.state("zoomed")  # Windows/Tk : démarre agrandie
        except tk.TclError:
            pass

        self._style_tabs()
        self._build_langbar()
        self._build_topbar()

        nb = ttk.Notebook(root)
        self.notebook = nb
        nb.pack(fill="both", expand=True, padx=8, pady=(0, 8))
        self.export_tab = ExportTab(nb, self)
        self.detail_tab = DetailTab(nb, self)
        self.import_tab = ImportTab(nb, self)
        self.profiles_tab = ProfilesTab(nb, self)
        self.journal_tab = JournalTab(nb, self)
        self.help_tab = HelpTab(nb, self)
        # Pastille de couleur par onglet pour les distinguer.
        self._tab_imgs = [self._swatch(c) for c in
                          (config.INVENTORY_TAB_COLOR, "#0ea5e9", "#1e40af",
                           config.PROFILE_TAB_COLOR, "#94a3b8", "#16a34a")]
        nb.add(self.export_tab, text=" " + i18n.t("tabs.inventory", "1. Inventaire du cas"),
               image=self._tab_imgs[0], compound="left")
        nb.add(self.detail_tab, text=" " + i18n.t("tabs.detail", "Détail du cas"),
               image=self._tab_imgs[1], compound="left")
        nb.add(self.import_tab, text=" " + i18n.t("tabs.import", "2. Import"),
               image=self._tab_imgs[2], compound="left")
        nb.add(self.profiles_tab, text=" " + i18n.t("tabs.profiles", "Profils"),
               image=self._tab_imgs[3], compound="left")
        nb.add(self.journal_tab, text=" " + i18n.t("tabs.journal", "Journal"),
               image=self._tab_imgs[4], compound="left")
        nb.add(self.help_tab, text=" " + i18n.t("tabs.help", "Aide"),
               image=self._tab_imgs[5], compound="left")

        root.protocol("WM_DELETE_WINDOW", self._on_close)
        self.log.log(f"{config.APP_NAME} {config.APP_VERSION} démarré.")
        if not self.var_exe.get():
            self.log.log("Chemin IntellaCmd.exe non encore mémorisé (sera enregistré au .ini).")
        # Crée le .ini à côté du script/exe s'il n'existe pas encore.
        if not os.path.exists(self.settings.path):
            self.save_settings()
            self.log.log(f"Fichier de configuration créé : {self.settings.path}")

    def _style_tabs(self):
        """Onglets plus visibles : titres en gras, plus d'espace."""
        style = ttk.Style(self.root)
        style.configure("TNotebook.Tab", font=("Segoe UI", 10, "bold"), padding=[16, 7])

    def _swatch(self, color: str, size: int = 14):
        """Petite image carrée de couleur, servant de pastille d'onglet."""
        img = tk.PhotoImage(master=self.root, width=size, height=size)
        img.put(color, to=(0, 0, size, size))
        return img

    # ------------------------------------------------------------------ #
    # Langue de l'interface (dossier lang\*.lang, choix mémorisé au .ini) #
    # ------------------------------------------------------------------ #
    def _init_language(self):
        # BASE_LANGUAGE (FR) réussit toujours (cf. i18n.load) : repli sûr même
        # si le fichier .lang choisi a été supprimé entre deux lancements.
        code = self.settings.get("language") or i18n.BASE_LANGUAGE
        if not i18n.load(code):
            i18n.load(i18n.BASE_LANGUAGE)

    def _build_langbar(self):
        """Sélecteur de langue, en haut à droite de la fenêtre."""
        bar = ttk.Frame(self.root)
        bar.pack(fill="x", padx=8, pady=(8, 0))
        ttk.Label(bar, text=i18n.t("topbar.language", "Langue") + " :").pack(
            side="right", padx=(4, 6))
        available = i18n.available_languages()
        self.var_lang = tk.StringVar(value=i18n.current_code())
        cb = ttk.Combobox(bar, textvariable=self.var_lang, state="readonly",
                          width=8, values=available)
        cb.pack(side="right")
        cb.bind("<<ComboboxSelected>>", self._on_language_change)

    def _on_language_change(self, _event=None):
        code = self.var_lang.get()
        self.settings.set("language", code)
        self.settings.save()
        # Charge la langue CIBLE avant le popup pour qu'il s'affiche déjà dans
        # cette langue (les widgets déjà construits, eux, ne se retraduisent
        # qu'au redémarrage — cf. limite tkinter documentée dans i18n.py).
        i18n.load(code)
        messagebox.showinfo(
            i18n.t("topbar.language", "Langue"),
            i18n.t("topbar.language_restart",
                   "La langue choisie sera appliquée au prochain démarrage de l'application."))

    def _build_topbar(self):
        bar = ttk.LabelFrame(self.root, text=i18n.t("topbar.title", "Paramètres communs"))
        bar.pack(fill="x", padx=8, pady=8)
        bar.columnconfigure(1, weight=1)

        # Utilisateur : lecture seule (récupéré dans case.xml du cas sélectionné).
        ttk.Label(bar, text=i18n.t("topbar.user", "Utilisateur (du cas)")).grid(
            row=0, column=0, sticky="w", padx=6, pady=4)
        ttk.Entry(bar, textvariable=self.var_user, state="readonly").grid(
            row=0, column=1, sticky="ew", padx=6, pady=4)

        ttk.Label(bar, text=i18n.t("topbar.exe", "IntellaCmd.exe *")).grid(
            row=1, column=0, sticky="w", padx=6, pady=4)
        if self._exe_locked:
            ttk.Entry(bar, textvariable=self.var_exe, state="readonly").grid(
                row=1, column=1, sticky="ew", padx=6, pady=4)
            ttk.Label(bar, text=i18n.t("topbar.exe_locked", "(verrouillé via .ini)"),
                     foreground="#64748b").grid(row=1, column=2, padx=6, pady=4)
        else:
            ttk.Entry(bar, textvariable=self.var_exe).grid(
                row=1, column=1, sticky="ew", padx=6, pady=4)
            make_button(bar, i18n.t("common.browse", "Parcourir…"), self._pick_exe).grid(
                row=1, column=2, padx=6, pady=4)

    def _pick_exe(self):
        f = filedialog.askopenfilename(
            title=i18n.t("topbar.exe_dialog", "IntellaCmd.exe"),
            filetypes=[("Exécutable", "*.exe"), ("Tous", "*.*")]
        )
        if f:
            self.var_exe.set(os.path.normpath(f))

    # ------------------------------------------------------------------ #
    # Métadonnées du cas (publiées par l'Inventaire, lues partout)       #
    # ------------------------------------------------------------------ #
    def set_case_meta(self, meta):
        """Enregistre les métadonnées du cas détecté et propage aux onglets."""
        self.case_meta = meta
        self.var_user.set(meta.get("user", ""))
        if hasattr(self, "detail_tab"):
            self.detail_tab.refresh()
        if hasattr(self, "import_tab"):
            self.import_tab.apply_case_meta()

    def open_profiles_with(self, values, suggested_name=""):
        """Bascule sur l'onglet Profils et pré-remplit le formulaire (Info Profil)."""
        self.profiles_tab.load_from_values(values, suggested_name)
        self.notebook.select(self.profiles_tab)

    def clear_case_meta(self):
        self.case_meta = None
        if hasattr(self, "detail_tab"):
            self.detail_tab.refresh()
        if hasattr(self, "import_tab"):
            self.import_tab.apply_case_meta()

    def save_settings(self):
        self.settings.set("user", self.var_user.get())
        self.settings.set("intellacmd_path", path_parser.clean_field(self.var_exe.get()))
        self.import_tab.persist(self.settings)
        self.settings.save()

    def _on_close(self):
        try:
            self.save_settings()
        finally:
            self.root.destroy()
