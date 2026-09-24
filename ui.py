"""Fenêtre principale : barre de contexte, fil d'étapes, pages, barre d'état.

Depuis la v3.0 (direction « Parcours », 11/09/2026), la navigation est dessinée
par ``ui_nav`` et le ``ttk.Notebook`` n'affiche plus ses onglets — il reste le
porteur des pages. Voir ``ui_nav`` pour le pourquoi de ce montage.
"""

import os
import subprocess
import sys
import tkinter as tk
from tkinter import filedialog, messagebox, ttk

import config
import i18n
import mime_catalog
import path_parser
import ui_nav
import ui_theme
from app_log import AppLog
from settings import Settings
from ui_detail import DetailTab
from ui_export import ExportTab
from ui_help import HelpTab
from ui_import import ImportTab
from ui_maintenance import MaintenanceTab
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

        # Référentiel des types MIME : rien n'est livré avec l'application (le
        # fichier de descriptions appartient à Vound et s'importe depuis
        # Maintenance). Son absence est un cas normal — `load` ne lève pas.
        mime_catalog.load()

        # Variables partagées entre onglets.
        # Utilisateur : LECTURE SEULE, issu de case.xml (rempli à la détection).
        self.var_user = tk.StringVar(value=self.settings.get("user"))
        self.var_exe = tk.StringVar(value=self.settings.get("intellacmd_path"))
        # IntellaCmd.exe verrouillé en GUI s'il est déjà mémorisé dans le .ini.
        self._exe_locked = bool(self.settings.get("intellacmd_path").strip())

        root.title(f"{i18n.t('app.title', config.APP_TITLE)} v{config.APP_VERSION}")
        # v3.0 : la barre « Paramètres communs » (2 lignes) et la ligne du
        # sélecteur de langue ont disparu, et les paramètres de l'Import se
        # replient — ~190 px rendus au travail. La fenêtre peut donc descendre
        # plus bas sans masquer les boutons d'action d'un écran de portable.
        root.geometry("1280x860")
        root.minsize(1000, 660)
        try:
            root.state("zoomed")  # Windows/Tk : démarre agrandie
        except tk.TclError:
            pass

        # Apparence : polices nommées, styles ttk, densité (cf. ui_theme).
        self.theme = ui_theme.Theme(
            root,
            density=self.settings.get("density", ui_theme.NORMAL),
            scale=self.settings.get("font_scale", "100"))

        self.context_bar = ui_nav.ContextBar(root, self)
        self.context_bar.pack(fill="x", side="top")
        self._build_context_detail()

        self.nav = ui_nav.StepNav(root, self, self._on_nav_select)
        self.nav.pack(fill="x", side="top")

        self.status = ui_nav.StatusBar(root, self)
        self.status.pack(fill="x", side="bottom")

        nb = ttk.Notebook(root, style="Headless.TNotebook")
        self.notebook = nb
        nb.pack(fill="both", expand=True, padx=self.theme.pad, pady=(self.theme.gap, 0))
        self.export_tab = ExportTab(nb, self)
        self.detail_tab = DetailTab(nb, self)
        self.import_tab = ImportTab(nb, self)
        self.profiles_tab = ProfilesTab(nb, self)
        # Le Journal vit désormais SOUS Maintenance (sous-onglets, 09/09/2026) :
        # `journal_tab` reste exposé pour qui le cherche, mais le sélectionner
        # passe obligatoirement par `aller_a()`.
        self.maintenance_tab = MaintenanceTab(nb, self)
        self.journal_tab = self.maintenance_tab.journal_tab
        self.help_tab = HelpTab(nb, self)
        # Les onglets du Notebook ne sont plus AFFICHÉS (style Headless), mais
        # leur texte reste utile : il nomme la page dans les messages d'erreur Tk
        # et sert de repli si le style venait à ne pas s'appliquer.
        for page, cle, defaut in (
                (self.export_tab, "tabs.inventory", "1. Inventaire du cas"),
                (self.detail_tab, "tabs.detail", "Détail du cas"),
                (self.import_tab, "tabs.import", "2. Import des sources"),
                (self.profiles_tab, "tabs.profiles", "Profils"),
                (self.maintenance_tab, "tabs.maintenance", "Maintenance"),
                (self.help_tab, "tabs.help", "Aide")):
            nb.add(page, text=i18n.t(cle, defaut))

        # Correspondance page ↔ identifiant de navigation (cf. ui_nav).
        self._nav_pages = {
            "inventaire": self.export_tab, "detail": self.detail_tab,
            "import": self.import_tab, "profils": self.profiles_tab,
            "maintenance": self.maintenance_tab, "aide": self.help_tab,
        }
        # Quel que soit le chemin emprunté pour changer de page — fil d'étapes,
        # `aller_a`, bouton « Info Profil → » d'un autre onglet — la navigation
        # doit refléter la page réellement affichée. Un seul point d'écoute.
        nb.bind("<<NotebookTabChanged>>", self._on_tab_changed)

        # Le cas memorise au .ini est detecte par ExportTab pendant sa
        # construction, quand les autres onglets n'existent pas encore : on
        # applique son type maintenant que le Notebook est complet.
        self._apply_case_kind()
        self.refresh_context()
        self.update_steps()
        self.nav.set_active("inventaire", 0)

        root.protocol("WM_DELETE_WINDOW", self._on_close)
        # ⚠ Ces trois lignes sont les PREMIÈRES du journal : les laisser en
        # français donnait un journal bilingue dès le démarrage en US.
        self.log.log(i18n.t("app.started_log", "{a} {v} démarré.",
                            a=config.APP_NAME, v=config.APP_VERSION))
        if not self.var_exe.get():
            self.log.log(i18n.t(
                "app.exe_unset_log",
                "Chemin IntellaCmd.exe non encore mémorisé (sera enregistré au .ini)."))
        # Crée le .ini à côté du script/exe s'il n'existe pas encore.
        if not os.path.exists(self.settings.path):
            self.save_settings()
            self.log.log(i18n.t("app.ini_created_log",
                                "Fichier de configuration créé : {p}",
                                p=self.settings.path))

    # ------------------------------------------------------------------ #
    # Navigation : fil d'étapes, contexte, état (cf. ui_nav)             #
    # ------------------------------------------------------------------ #
    def _on_nav_select(self, tab_id: str, step_index=None):
        """Un clic dans le fil d'étapes ou dans les outils."""
        page = self._nav_pages.get(tab_id)
        if page is None:
            return
        try:
            self.notebook.select(page)
        except tk.TclError:
            return                      # page grisée (cas compound)
        self.nav.set_active(tab_id, step_index)

    def _on_tab_changed(self, _event=None):
        courant = self.notebook.select()
        for tab_id, page in self._nav_pages.items():
            if str(page) == courant:
                actif = self.nav._active or (None, None)
                step = actif[1] if actif[0] == tab_id else None
                self.nav.set_active(tab_id, step)
                break
        self.update_steps()

    def refresh_context(self):
        """Recopie l'état du cas dans la barre de contexte (une ligne).

        🐞 Le dossier du cas s'appelle **`folder`** dans `case_meta.read_case`,
        pas `path` (`path` n'existe que sur une entrée de SOUS-cas). La clé
        fautive rendait toujours `""`, donc la barre retombait sur `last_case`
        du `.ini` — c'est-à-dire le cas **précédent** tant que les paramètres
        n'avaient pas été réenregistrés : en changeant de cas sans fermer
        l'application, la ligne du haut affichait l'ancien chemin (constaté en
        réel sur la v3.1b). Le repli sur le `.ini` n'a de sens qu'au démarrage,
        avant qu'un cas soit lu.
        """
        meta = self.case_meta or {}
        self.context_bar.refresh(
            case_name=meta.get("name", "") or "",
            case_path=meta.get("folder", "") or self.settings.get("last_case", ""),
            user=self.var_user.get(), exe=self.var_exe.get().strip())

    def update_steps(self):
        """Avancement du parcours : cas lu → sources analysées → import vérifié.

        C'est ce qui donne son sens au fil : trois libellés qui ne changeraient
        jamais ne seraient qu'une barre d'onglets déguisée.
        """
        if not hasattr(self, "nav") or not hasattr(self, "import_tab"):
            return
        compound = self.is_compound_case()
        cas_lu = bool(self.case_meta)
        valide = bool(getattr(self.import_tab, "_last_validation_ok", False))

        self.nav.set_step_state(0, ui_nav.DONE if cas_lu else ui_nav.TODO)
        if compound:
            # Un compound ne peut pas recevoir de source : l'étape d'import n'a
            # pas de sens, elle est barrée.
            self.nav.set_step_state(1, ui_nav.BLOCKED)
            return
        # « Faite » = les sources ont été retrouvées dans le cas après import.
        # La mesure seule ne suffit pas : rien n'est encore importé, et une
        # étape verte le laisserait croire.
        self.nav.set_step_state(1, ui_nav.DONE if valide else ui_nav.TODO)

    def set_status(self, text: str, level: str = "ok"):
        """Message de la barre d'état (bas de fenêtre), visible sur tout écran."""
        if hasattr(self, "status"):
            self.status.set_status(text, level)

    def set_status_summary(self, text: str):
        if hasattr(self, "status"):
            self.status.set_summary(text)

    # ------------------------------------------------------------------ #
    # Langue de l'interface (dossier lang\*.lang, choix mémorisé au .ini) #
    # ------------------------------------------------------------------ #
    def _init_language(self):
        # BASE_LANGUAGE (FR) réussit toujours (cf. i18n.load) : repli sûr même
        # si le fichier .lang choisi a été supprimé entre deux lancements.
        code = self.settings.get("language") or i18n.BASE_LANGUAGE
        if not i18n.load(code):
            i18n.load(i18n.BASE_LANGUAGE)

    def change_language(self, code: str) -> None:
        """Change la langue de l'interface (appelée par Maintenance → Options).

        Le sélecteur a quitté la barre du haut en v3.0 : il s'applique au
        redémarrage, c'est donc un réglage et non une commande — sa place est
        avec les autres réglages, pas sur une ligne réservée de chaque écran.
        """
        if not code or code == i18n.current_code():
            return
        self._on_language_change(code)

    def _on_language_change(self, code: str):
        self.settings.set("language", code)
        self.settings.save()
        # Charge la langue CIBLE avant le popup pour qu'il s'affiche déjà dans
        # cette langue (les widgets déjà construits, eux, ne se retraduisent
        # qu'au redémarrage — cf. limite tkinter documentée dans i18n.py).
        i18n.load(code)
        title = i18n.t("topbar.language", "Langue")
        # Le redémarrage repart d'une application vierge : une liste de sources
        # en cours de préparation serait perdue sans prévenir (08/09/2026).
        # On le dit AVANT, et on laisse la possibilité de l'exporter d'abord.
        tab = getattr(self, "import_tab", None)
        en_cours = len(getattr(tab, "sources", []) or []) if tab else 0
        if en_cours and not messagebox.askyesno(title, i18n.t(
                "topbar.language_lose_work",
                "{n} source(s) sont listées dans l'onglet « Import ». Le "
                "redémarrage les perd.\n\nExportez la liste d'abord "
                "(« Exporter la liste… ») si vous voulez la retrouver.\n\n"
                "Continuer quand même ?", n=en_cours)):
            return
        if messagebox.askyesno(title, i18n.t(
                "topbar.language_restart_ask",
                "La langue choisie ne s'applique qu'au démarrage de l'application "
                "(les fenêtres déjà ouvertes gardent leurs textes).\n\n"
                "Redémarrer IntellaFeeder maintenant ?")):
            self._restart()
        else:
            messagebox.showinfo(title, i18n.t(
                "topbar.language_restart",
                "La langue choisie sera appliquée au prochain démarrage de l'application."))

    def _restart(self):
        """Relance l'application puis ferme l'instance courante.

        Mode « frozen » (exe PyInstaller) : ``sys.executable`` EST l'application.
        En mode script, il pointe sur python.exe et il faut lui repasser le
        script. Les paramètres sont enregistrés avant, comme à une fermeture
        normale.

        🐞 **L'environnement PyInstaller doit être PURGÉ** avant de relancer un
        exe onefile (bug des 07-08/09/2026). Le bootloader transmet à son
        processus applicatif ``_PYI_APPLICATION_HOME_DIR`` (et ``_MEIPASS2``
        avant PyInstaller 6), qui désigne le dossier temporaire ``_MEIxxxx`` où
        l'exe s'est extrait. Ces variables **s'héritent** : le processus relancé
        réutilisait le ``_MEI`` de son parent au lieu de faire le sien.

        D'où le symptôme exact, vérifié en isolant le mécanisme dans un exe
        d'essai : **le 1er redémarrage passe** (le nouveau processus a déjà tout
        chargé en mémoire quand le dossier disparaît), **le 2e échoue** sur
        « interpréteur Python introuvable » — il pointe vers un ``_MEI`` que le
        processus d'origine a supprimé en mourant. Purger ces variables rend à
        chaque relance sa propre extraction (constaté : 5 dossiers distincts au
        lieu d'un seul partagé).

        Le répertoire courant n'est pas transmis non plus : on démarre dans
        ``config.base_dir()``, qui existe toujours.
        """
        cmd = []
        try:
            self.save_settings()
            if getattr(sys, "frozen", False):
                cmd = [sys.executable] + sys.argv[1:]
            else:
                cmd = [sys.executable, os.path.abspath(sys.argv[0])] + sys.argv[1:]
            env = {k: v for k, v in os.environ.items()
                   if not k.startswith("_PYI") and k != "_MEIPASS2"}
            depart = config.base_dir()
            if not os.path.isdir(depart):
                depart = None            # laisse Windows choisir plutôt qu'échouer
            self.log.log(i18n.t("topbar.restart_log", "Redémarrage : {c}",
                                c=subprocess.list2cmdline(cmd)))
            subprocess.Popen(cmd, cwd=depart, env=env)
        except (OSError, ValueError) as exc:
            messagebox.showerror(
                i18n.t("topbar.language", "Langue"),
                i18n.t("topbar.restart_failed",
                       "Redémarrage impossible :\n{e}\n\nFermez puis rouvrez "
                       "l'application pour appliquer la langue.", e=exc))
            return
        self.root.destroy()

    def _build_context_detail(self):
        """Volet dépliable de la barre de contexte : les champs eux-mêmes.

        Ce sont les anciens « Paramètres communs ». Ils restent modifiables,
        mais ne coûtent plus deux lignes en permanence sur les six écrans.
        """
        bar = self.context_bar.detail
        pad = self.theme.pad
        inner = ttk.Frame(bar, style="Soft.TFrame")
        inner.pack(fill="x", padx=pad, pady=self.theme.gap)
        inner.columnconfigure(1, weight=1)

        # Utilisateur : lecture seule (récupéré dans case.xml du cas sélectionné).
        ttk.Label(inner, text=i18n.t("topbar.user", "Utilisateur (du cas)"),
                  style="Soft.TLabel").grid(row=0, column=0, sticky="w", padx=6, pady=3)
        ttk.Entry(inner, textvariable=self.var_user, state="readonly").grid(
            row=0, column=1, sticky="ew", padx=6, pady=3)

        ttk.Label(inner, text=i18n.t("topbar.exe", "IntellaCmd.exe *"),
                  style="Soft.TLabel").grid(row=1, column=0, sticky="w", padx=6, pady=3)
        if self._exe_locked:
            ttk.Entry(inner, textvariable=self.var_exe, state="readonly").grid(
                row=1, column=1, sticky="ew", padx=6, pady=3)
            ttk.Label(inner, text=i18n.t("topbar.exe_locked", "(verrouillé via .ini)"),
                      style="Soft.TLabel").grid(row=1, column=2, padx=6, pady=3)
        else:
            ttk.Entry(inner, textvariable=self.var_exe).grid(
                row=1, column=1, sticky="ew", padx=6, pady=3)
            make_button(inner, i18n.t("common.browse", "Parcourir…"),
                        self._pick_exe).grid(row=1, column=2, padx=6, pady=3)
        self.var_exe.trace_add("write", lambda *_: self.refresh_context())

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
        self._apply_case_kind()
        if hasattr(self, "detail_tab"):
            self.detail_tab.refresh()
        if hasattr(self, "import_tab"):
            self.import_tab.apply_case_meta()
        self.refresh_context()
        self.update_steps()
        nom = meta.get("name", "")
        if nom:
            self.set_status(i18n.t("status.case_loaded", "Cas « {n} » chargé.", n=nom))
            self.set_status_summary(_resume_cas(meta))

    def is_compound_case(self) -> bool:
        """Le cas sélectionné est-il un cas compound (import impossible) ?"""
        return bool(self.case_meta and self.case_meta.get("is_compound"))

    def _apply_case_kind(self):
        """Grise l'onglet Import sur un cas compound, le rétablit sinon.

        Un compound ne fait que référencer des sous-cas : IntellaCmd refuse d'y
        ajouter une source (il faut viser un sous-cas). Seuls « Inventaire du
        cas » et « Détail du cas » ont un sens. Le grisage prévient l'utilisateur
        avant qu'il ne remplisse une liste inutilisable ; ``ImportTab`` refuse en
        plus les actions (double garde, comme pour le verrou de mesure).
        """
        # ExportTab detecte le cas memorise des sa construction, donc AVANT que
        # les onglets suivants existent : sans cette garde, tout demarrage avec
        # un `last_case` au .ini planterait.
        if not hasattr(self, "import_tab"):
            return
        compound = self.is_compound_case()
        try:
            self.notebook.tab(self.import_tab, state="disabled" if compound else "normal")
        except tk.TclError:
            return
        # Les étapes 2 et 3 du fil deviennent barrées : un compound ne peut pas
        # recevoir de source, et une étape cliquable qui refuse d'agir serait
        # plus déroutante qu'une étape visiblement hors jeu.
        if hasattr(self, "nav"):
            self.nav.set_enabled("import", not compound)
        # Un onglet désactivé alors qu'il est affiché reste à l'écran : on
        # ramène l'utilisateur sur l'Inventaire, d'où vient la sélection du cas.
        if compound and self.notebook.select() == str(self.import_tab):
            self.aller_a(self.export_tab)

    def aller_a(self, onglet) -> None:
        """Affiche un onglet, **où qu'il soit** — premier niveau ou sous-onglet.

        Depuis que le Journal vit sous Maintenance, un ``notebook.select()``
        direct échoue sur un onglet imbriqué. Un seul point de passage évite que
        chaque nouvel appel réinvente la descente et qu'un seul l'oublie.
        """
        try:
            if str(onglet) in self.notebook.tabs():
                self.notebook.select(onglet)
                return
            if hasattr(self, "maintenance_tab") \
                    and self.maintenance_tab.select_child(onglet):
                self.notebook.select(self.maintenance_tab)
        except tk.TclError:
            pass

    def open_profiles_with(self, values, suggested_name="", src=None):
        """Bascule sur l'onglet Profils et pré-remplit le formulaire (Info Profil).

        ``src`` = la source de l'export dont viennent les valeurs : elle suit,
        pour que « Voir les réglages… » puisse dire ce qui n'est PAS repris.
        """
        self.profiles_tab.load_from_values(values, suggested_name, src)
        self.aller_a(self.profiles_tab)

    def clear_case_meta(self):
        self.case_meta = None
        self._apply_case_kind()
        self.refresh_context()
        self.update_steps()
        self.set_status_summary("")
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


def _resume_cas(meta) -> str:
    """Résumé du cas pour la droite de la barre d'état (nom, sources, volume)."""
    morceaux = [meta.get("name", "")]
    taille = meta.get("size")
    if taille:
        morceaux.append(config.human_size(taille))
    if meta.get("is_compound"):
        morceaux.append(i18n.t("status.compound", "cas compound"))
    return "  —  ".join(m for m in morceaux if m)
