"""Onglet Import : collage des sources, récapitulatif (tailles + tâches), génération.

Le cas cible (emplacement + nom + utilisateur) est **verrouillé** : il provient de
l'onglet « 1. Inventaire du cas » (lecture de ``case.xml``). La sortie est
automatique : ``Script\\Cas\\<nom>\\scripts`` (+ ``logs``). Le bouton « Valider les
opérations » recroise un re-scan du cas et l'analyse des logs d'import.
"""

import csv
import json
import os
import re
import threading
import tkinter as tk
from tkinter import filedialog, messagebox, ttk

import case_export
import case_info
import config
import generator
import i18n
import models
import op_validation
import path_parser
import profiles
import sizing
import task_builder
import validation
from ui_widgets import Tooltip, make_button

_LEAD_COLS = ("import",)            # case à cocher « Importer »
_BASE_COLS = ("name", "type", "size", "profile")
_TRAIL_COLS = ("del",)              # croix de suppression de ligne
_DEL_GLYPH = "✕"


class ImportTab(ttk.Frame):
    def __init__(self, parent, app):
        super().__init__(parent)
        self.app = app
        self.sources = []          # list[models.Source]
        self.tasks = []            # list[{id,name,obj}]
        self._tasks_from_case = False  # tâches issues de l'inventaire (recyclage) ?
        self._sort_col = None
        self._sort_asc = True
        self._heading_base = {}    # colid -> texte d'en-tête de base

        self._build_params()
        self._build_panels()
        self._build_recap()
        self._build_actions()
        self._load_tasks(show_error=False)  # tâches par défaut au démarrage
        self.apply_case_meta()              # reflète un cas déjà détecté

    # ------------------------------------------------------------------ #
    def _build_params(self):
        s = self.app.settings
        frame = ttk.LabelFrame(self, text=i18n.t(
            "import.target_case_frame", "Cas cible (défini par l'onglet « 1. Inventaire du cas »)"))
        frame.pack(fill="x", padx=8, pady=(8, 4))
        frame.columnconfigure(1, weight=1)
        frame.columnconfigure(3, weight=2)

        # Verrouillés : renseignés depuis case.xml via apply_case_meta().
        self.var_case = tk.StringVar(value=s.get("last_case"))
        self.var_casename = tk.StringVar(value=s.get("casename"))
        # Modifiables :
        self.var_tasks = tk.StringVar(value=s.get("tasks_path") or config.default_tasks_path())
        self.var_tz = tk.StringVar(value=s.get("timezone") or config.DEFAULT_TIMEZONE)
        self.var_limit = tk.StringVar(value=s.get("limit_gb") or str(config.DEFAULT_SIZE_LIMIT_GB))
        self.var_extra = tk.StringVar(value=s.get("extra"))

        ttk.Label(frame, text=i18n.t("import.case_label", "Cas :")).grid(
            row=0, column=0, sticky="w", padx=6, pady=4)
        ttk.Entry(frame, textvariable=self.var_casename, state="readonly").grid(
            row=0, column=1, sticky="ew", padx=6, pady=4)
        ttk.Label(frame, text=i18n.t("import.location_label", "Emplacement :")).grid(
            row=0, column=2, sticky="e", padx=6, pady=4)
        ttk.Entry(frame, textvariable=self.var_case, state="readonly").grid(
            row=0, column=3, sticky="ew", padx=6, pady=4)

        ttk.Label(frame, text=i18n.t("import.limit_label", "Limite / cas (Go)")).grid(
            row=1, column=0, sticky="w", padx=6, pady=4)
        ttk.Entry(frame, textvariable=self.var_limit, width=8).grid(row=1, column=1, sticky="w", padx=6, pady=4)
        ttk.Label(frame, text=i18n.t("import.timezone_label", "Fuseau horaire")).grid(
            row=1, column=2, sticky="e", padx=6, pady=4)
        ttk.Combobox(frame, textvariable=self.var_tz, values=config.TIMEZONES, width=16).grid(
            row=1, column=3, sticky="w", padx=6, pady=4)

        ttk.Label(frame, text=i18n.t("import.tasks_file_label", "Fichier de tâches")).grid(
            row=2, column=0, sticky="w", padx=6, pady=4)
        ttk.Entry(frame, textvariable=self.var_tasks).grid(row=2, column=1, columnspan=2, sticky="ew", padx=6, pady=4)
        make_button(frame, i18n.t("common.browse", "Parcourir…"), self._pick_tasks).grid(
            row=2, column=3, sticky="w", padx=6, pady=4)

        ttk.Label(frame, text=i18n.t("common.extra_args", "Arguments suppl.")).grid(
            row=3, column=0, sticky="w", padx=6, pady=4)
        ttk.Entry(frame, textvariable=self.var_extra).grid(row=3, column=1, columnspan=3, sticky="ew", padx=6, pady=4)

        # Bug Vound confirmé sur les images forensiques multi-tronçons : option
        # pour ne pas vérifier l'intégrité (validateDiskImage:false). État
        # mémorisé par cas dans IF_<cas>.info.
        self.var_skip_integrity = tk.BooleanVar(value=False)
        chk = ttk.Checkbutton(
            frame, variable=self.var_skip_integrity,
            text=i18n.t("import.skip_integrity",
                       "Ne pas vérifier l'intégrité des sources "
                       "(images multi-tronçons — contourne le bug Vound)"),
            command=self._on_skip_integrity_toggle)
        chk.grid(row=4, column=0, columnspan=4, sticky="w", padx=6, pady=(0, 4))

    def _build_panels(self):
        frame = ttk.Frame(self)
        frame.pack(fill="both", expand=False, padx=8, pady=4)
        frame.columnconfigure(0, weight=1)
        frame.columnconfigure(1, weight=1)

        left = ttk.LabelFrame(frame, text=i18n.t(
            "import.images_panel", "Images forensiques (DISK_IMAGE) — 1 chemin/ligne"))
        left.grid(row=0, column=0, sticky="nsew", padx=(0, 5))
        self.txt_images = self._build_paste_text(left)

        right = ttk.LabelFrame(frame, text=i18n.t(
            "import.folders_panel", "Dossiers standard (FOLDER_OR_FILE) — 1 chemin/ligne"))
        right.grid(row=0, column=1, sticky="nsew", padx=(5, 0))
        self.txt_folders = self._build_paste_text(right)

    @staticmethod
    def _build_paste_text(parent):
        """Zone de collage (1 chemin/ligne) avec défilement vertical ET horizontal."""
        holder = ttk.Frame(parent)
        holder.pack(fill="both", expand=True, padx=4, pady=4)
        txt = tk.Text(holder, height=6, wrap="none", undo=True)
        vsb = ttk.Scrollbar(holder, orient="vertical", command=txt.yview)
        hsb = ttk.Scrollbar(holder, orient="horizontal", command=txt.xview)
        txt.configure(yscrollcommand=vsb.set, xscrollcommand=hsb.set)
        txt.grid(row=0, column=0, sticky="nsew")
        vsb.grid(row=0, column=1, sticky="ns")
        hsb.grid(row=1, column=0, sticky="ew")
        holder.rowconfigure(0, weight=1)
        holder.columnconfigure(0, weight=1)
        return txt

    def _build_recap(self):
        frame = ttk.LabelFrame(self, text=i18n.t("import.recap_frame", "Récapitulatif des sources"))
        frame.pack(fill="both", expand=True, padx=8, pady=4)

        # Barre d'outils sur 2 lignes : ligne 1 = tout ce qui concerne les SOURCES,
        # ligne 2 = tout ce qui concerne les TÂCHES.
        toolbar = ttk.Frame(frame)
        toolbar.pack(fill="x", padx=4, pady=(4, 0))
        make_button(toolbar, i18n.t("import.summarize", "▼ Récapituler"), self.recapituler).pack(side="left")
        make_button(toolbar, i18n.t("import.compute_size", "Calculer la taille"),
                   self.calculer_taille).pack(side="left", padx=6)
        make_button(toolbar, i18n.t("import.export_list", "Exporter la liste…"),
                   self._export_recap).pack(side="left")
        make_button(toolbar, i18n.t("import.import_list", "Importer une liste…"),
                   self._import_recap).pack(side="left", padx=4)
        ttk.Separator(toolbar, orient="vertical").pack(side="left", fill="y", padx=8)
        make_button(toolbar, i18n.t("import.check_all", "Imp. : tout cocher"),
                   lambda: self._set_all_import(True)).pack(side="left")
        make_button(toolbar, i18n.t("import.uncheck_all", "Imp. : tout décocher"),
                   lambda: self._set_all_import(False)).pack(side="left", padx=4)
        ttk.Separator(toolbar, orient="vertical").pack(side="left", fill="y", padx=8)
        # Profil par défaut : choisir un profil l'applique à TOUTES les lignes.
        ttk.Label(toolbar, text=i18n.t("import.default_profile_label", "Profil par défaut :")).pack(side="left")
        self.cb_default_profile = ttk.Combobox(toolbar, state="readonly", width=18,
                                               postcommand=self._refresh_default_profiles)
        self.cb_default_profile.set(profiles.DEFAULT_NAME)
        self.cb_default_profile.pack(side="left", padx=4)
        self.cb_default_profile.bind("<<ComboboxSelected>>", lambda _e: self._apply_profile_all())

        toolbar2 = ttk.Frame(frame)
        toolbar2.pack(fill="x", padx=4, pady=(2, 4))
        make_button(toolbar2, i18n.t("import.reload_tasks", "Recharger les tâches"),
                   lambda: self._load_tasks(show_error=True)).pack(side="left")
        # Couleur de l'onglet « Inventaire du cas » : ce bouton recycle les tâches
        # lues dans l'inventaire.
        make_button(toolbar2, i18n.t("import.case_tasks", "Tâches du cas (inventaire)"),
                   self._use_case_tasks, color=config.INVENTORY_TAB_COLOR).pack(side="left", padx=4)
        ttk.Separator(toolbar2, orient="vertical").pack(side="left", fill="y", padx=8)
        make_button(toolbar2, i18n.t("import.tasks_check_all", "Tâches : tout cocher"),
                   lambda: self._set_all(True)).pack(side="left")
        make_button(toolbar2, i18n.t("import.tasks_uncheck_all", "Tâches : tout décocher"),
                   lambda: self._set_all(False)).pack(side="left", padx=4)
        # Boutons de sélection par tâche (reconstruits dynamiquement) :
        self.col_btns = ttk.Frame(toolbar2)
        self.col_btns.pack(side="left", padx=8)

        holder = ttk.Frame(frame)
        holder.pack(fill="both", expand=True, padx=4, pady=4)
        self.tree = ttk.Treeview(holder, columns=_LEAD_COLS + _BASE_COLS + _TRAIL_COLS,
                                 show="headings", selectmode="none")
        vsb = ttk.Scrollbar(holder, orient="vertical", command=self.tree.yview)
        hsb = ttk.Scrollbar(holder, orient="horizontal", command=self.tree.xview)  # slide horizontal
        self.tree.configure(yscrollcommand=vsb.set, xscrollcommand=hsb.set)
        self.tree.grid(row=0, column=0, sticky="nsew")
        vsb.grid(row=0, column=1, sticky="ns")
        hsb.grid(row=1, column=0, sticky="ew")
        holder.rowconfigure(0, weight=1)
        holder.columnconfigure(0, weight=1)

        # Surlignage des sources déjà présentes dans le cas (inventaire).
        self.tree.tag_configure("dup", background="#ffd9d9")

        self.tooltip = Tooltip(self.tree)
        self.tree.bind("<Button-1>", self._on_click)
        self.tree.bind("<Double-1>", self._on_double_click)
        self.tree.bind("<Motion>", self._on_motion)
        self.tree.bind("<Leave>", lambda _e: self.tooltip.hide())

        self.lbl_total = ttk.Label(frame, text=i18n.t("import.zero_sources", "0 source"))
        self.lbl_total.pack(anchor="w", padx=6, pady=(0, 2))
        self.lbl_inventory = ttk.Label(frame, text="", foreground="#64748b")
        self.lbl_inventory.pack(anchor="w", padx=6, pady=(0, 4))

    def _build_actions(self):
        # Ordre visuel gauche → droite : Générer | Importer | Valider.
        bar = ttk.Frame(self)
        bar.pack(fill="x", padx=8, pady=(0, 8))
        # « Générer » = action principale → vert (primary) ; les autres en style standard.
        make_button(bar, i18n.t("import.generate", "Générer les fichiers d'import"), self.generer,
                    color="#16a34a").pack(side="left")
        self.btn_validate = make_button(bar, i18n.t("import.validate", "Valider les opérations"),
                                        self.valider_operations)
        self.btn_validate.pack(side="right", padx=6)
        self.btn_import = make_button(bar, i18n.t("import.run_import", "Importer (lancer le .bat)"),
                                      self.importer)
        self.btn_import.pack(side="right", padx=6)

    # ------------------------------------------------------------------ #
    # Cas cible (verrouillé, depuis l'inventaire / case.xml)             #
    # ------------------------------------------------------------------ #
    def apply_case_meta(self):
        """Renseigne le cas cible (verrouillé) depuis ``app.case_meta``."""
        meta = self.app.case_meta
        if meta:
            self.var_case.set(meta["folder"])
            self.var_casename.set(meta["name"])
            # Réglage d'intégrité mémorisé pour ce cas (IF_<cas>.info).
            self.var_skip_integrity.set(
                case_info.get_skip_integrity(meta["folder"], meta["name"]))
        else:
            self.var_case.set("")
            self.var_casename.set("")
            self.var_skip_integrity.set(False)
        # Reflète l'état dans le champ « Arguments suppl. » (cocher = y mettre
        # « -validateDiskImage false »).
        self._sync_integrity_arg()
        self._refresh_tree()

    # Argument CLI ajouté/retiré du champ « Arguments suppl. » par la case
    # « ne pas vérifier l'intégrité » (option `-vdi`, manuel p.4).
    _INTEGRITY_ARG = "-validateDiskImage false"
    _INTEGRITY_RE = re.compile(r"\s*-validateDiskImage\s+\S+", re.IGNORECASE)

    def _sync_integrity_arg(self):
        """Met le champ « Arguments suppl. » en cohérence avec la case à cocher :
        retire toute occurrence existante puis ajoute l'argument si la case est
        cochée (idempotent)."""
        cur = self._INTEGRITY_RE.sub("", self.var_extra.get() or "").strip()
        if self.var_skip_integrity.get():
            cur = (cur + " " + self._INTEGRITY_ARG).strip() if cur else self._INTEGRITY_ARG
        self.var_extra.set(cur)

    def _on_skip_integrity_toggle(self):
        """Coche/décoche « ne pas vérifier l'intégrité » : met à jour le champ
        « Arguments suppl. » et mémorise l'état dans IF_<cas>.info."""
        meta = self.app.case_meta
        if not meta:
            messagebox.showinfo(
                i18n.t("import.integrity_title", "Intégrité des sources"),
                i18n.t("import.select_case_first",
                      "Sélectionnez d'abord un cas (onglet « 1. Inventaire du cas »)."))
            self.var_skip_integrity.set(False)
            return
        val = self.var_skip_integrity.get()
        self._sync_integrity_arg()
        case_info.set_skip_integrity(meta["folder"], meta["name"], val)
        self.app.log.log(i18n.t("import.integrity_check_log", "Vérification d'intégrité des sources : ")
                         + (i18n.t("import.integrity_disabled_log",
                                  "DÉSACTIVÉE (« {a} » ajouté aux arguments).", a=self._INTEGRITY_ARG)
                            if val else i18n.t("import.integrity_enabled_log", "activée (argument retiré).")))

    # ------------------------------------------------------------------ #
    # Tâches : chargement + colonnes dynamiques                          #
    # ------------------------------------------------------------------ #
    def _load_tasks(self, show_error: bool):
        self._tasks_from_case = False  # provenance = fichier de l'onglet
        title = i18n.t("import.tasks_file_title", "Fichier de tâches")
        path = path_parser.clean_field(self.var_tasks.get())
        if not path or not os.path.isfile(path):
            self.tasks = []
            self._rebuild_columns()
            if show_error:
                messagebox.showerror(title, i18n.t("import.tasks_file_not_found", "Introuvable :\n{p}", p=path))
            return False
        try:
            self.tasks = task_builder.load_tasks(path)
            self._rebuild_columns()
            self.app.log.log(i18n.t(
                "import.tasks_file_loaded_log", "Fichier de tâches chargé : {n} tâche(s).",
                n=len(self.tasks)))
            return True
        except Exception as exc:
            self.tasks = []
            self._rebuild_columns()
            self.app.log.log(i18n.t(
                "import.tasks_file_read_error_log", "Erreur lecture fichier de tâches : {e}", e=exc),
                level="ERROR")
            if show_error:
                messagebox.showerror(title, i18n.t(
                    "import.tasks_file_unreadable", "Lecture impossible :\n{e}", e=exc))
            return False

    def _use_case_tasks(self):
        """Recycle les tâches déjà présentes sur les sources du cas (inventaire).

        Le bloc ``<tasks>`` de chaque source de l'export ``-exportSourceList`` est
        la définition complète (format ``tasks.json``) ; l'inventaire en agrège
        l'union dédupliquée (`case_tasks`). On les charge comme jeu de tâches
        courant, sans fichier externe.
        """
        title = i18n.t("import.case_tasks", "Tâches du cas (inventaire)")
        inv = self.app.inventory
        if not (inv and self._inventory_matches()):
            messagebox.showinfo(title, i18n.t(
                "import.case_tasks_not_loaded",
                "La liste des sources du cas n'est pas chargée.\n"
                "Lancez « Lire les sources » dans l'onglet « 1. Inventaire du cas »."))
            return
        objs = inv.get("case_tasks") or []
        if not objs:
            messagebox.showinfo(title, i18n.t(
                "import.case_tasks_none", "Aucune tâche n'est définie sur les sources de ce cas."))
            return
        try:
            self.tasks = task_builder.tasks_from_objs(objs)
        except ValueError as exc:
            messagebox.showerror(title, i18n.t(
                "import.case_tasks_unreadable", "Tâches illisibles :\n{e}", e=exc))
            return
        self._tasks_from_case = True
        self._rebuild_columns()
        self.app.log.log(i18n.t(
            "import.case_tasks_recycled_log", "Tâches recyclées depuis l'inventaire du cas : {n} tâche(s).",
            n=len(self.tasks)))
        messagebox.showinfo(title, i18n.t(
            "import.case_tasks_recycled_msg",
            "{n} tâche(s) du cas chargée(s) (dédupliquées).\n"
            "Elles s'appliquent comme un fichier de tâches : cochez-les par source.",
            n=len(self.tasks)))

    def _task_colid(self, i):
        return f"task_{i}"

    def _rebuild_columns(self):
        cols = (list(_LEAD_COLS) + list(_BASE_COLS)
                + [self._task_colid(i) for i in range(len(self.tasks))]
                + list(_TRAIL_COLS))
        self.tree["columns"] = cols

        self._heading_base = {
            "import": i18n.t("import.col_import", "Imp."),
            "name": i18n.t("import.col_name", "Nom de la source"),
            "type": i18n.t("col.type", "Type"),
            "size": i18n.t("col.size", "Taille"),
            "profile": i18n.t("import.col_profile", "Profil"),
            "del": i18n.t("import.col_delete", "Suppr."),
        }
        for i, t in enumerate(self.tasks):
            self._heading_base[self._task_colid(i)] = f"T{i + 1}"

        for c in cols:
            self.tree.heading(c, text=self._heading_base[c], command=lambda col=c: self._sort_by(col))
        self.tree.column("import", width=48, anchor="center", stretch=False)
        self.tree.column("name", width=320, anchor="w", stretch=True)
        self.tree.column("type", width=80, anchor="center", stretch=False)
        self.tree.column("size", width=90, anchor="e", stretch=False)
        self.tree.column("profile", width=120, anchor="w", stretch=False)
        for i in range(len(self.tasks)):
            self.tree.column(self._task_colid(i), width=64, anchor="center", stretch=False)
        self.tree.column("del", width=52, anchor="center", stretch=False)

        self._rebuild_col_buttons()
        self._refresh_tree()

    def _rebuild_col_buttons(self):
        for w in self.col_btns.winfo_children():
            w.destroy()
        for i, t in enumerate(self.tasks):
            b_on = make_button(self.col_btns, f"T{i + 1} ✓", lambda idx=i: self._toggle_column(idx, True),
                               width=4, padx=4)
            b_off = make_button(self.col_btns, f"T{i + 1} ✗", lambda idx=i: self._toggle_column(idx, False),
                                width=4, padx=4)
            b_on.pack(side="left", padx=(6, 0))
            b_off.pack(side="left", padx=(0, 2))
            self._bind_tip(b_on, t["name"])
            self._bind_tip(b_off, t["name"])

    def _bind_tip(self, widget, text):
        widget.bind("<Enter>", lambda e, txt=text: self.tooltip.show(txt, e.x_root + 12, e.y_root + 12))
        widget.bind("<Leave>", lambda _e: self.tooltip.hide())

    # ------------------------------------------------------------------ #
    # Sélecteurs                                                         #
    # ------------------------------------------------------------------ #
    def _pick_tasks(self):
        f = filedialog.askopenfilename(
            title=i18n.t("import.tasks_file_title", "Fichier de tâches"),
            filetypes=[("JSON", "*.json"), (i18n.t("common.filetype_all", "Tous"), "*.*")])
        if f:
            self.var_tasks.set(os.path.normpath(f))
            self._load_tasks(show_error=True)

    # ------------------------------------------------------------------ #
    # Récapitulatif                                                      #
    # ------------------------------------------------------------------ #
    def recapituler(self):
        prev = {s.path.lower(): s for s in self.sources}
        parsed = []
        parsed += path_parser.parse_lines(self.txt_images.get("1.0", "end"), config.SOURCE_TYPE_DISK_IMAGE)
        parsed += path_parser.parse_lines(self.txt_folders.get("1.0", "end"), config.SOURCE_TYPE_FOLDER)

        seen, merged = set(), []
        for s in parsed:
            key = s.path.lower()
            if key in seen:
                continue
            seen.add(key)
            old = prev.get(key)
            if old is not None:
                s.selected_task_ids = set(old.selected_task_ids)
                s.name, s.size_bytes = old.name, old.size_bytes
                s.import_selected = old.import_selected
                s.profile = getattr(old, "profile", "défaut")
            merged.append(s)

        self.sources = merged
        self._sort_col = None
        removed = self._drop_indexed()  # retrait auto des déjà indexées
        self._refresh_tree()
        msg = i18n.t("import.summary_log", "Récapitulatif : {n} source(s).", n=len(self.sources))
        if removed:
            msg += " " + i18n.t("import.summary_removed_log", "{n} déjà dans le cas, retirée(s).", n=removed)
        self.app.log.log(msg)

    def _size_text(self, s):
        return config.human_size(s.size_bytes) if s.size_bytes is not None else "—"

    def _row_values(self, s):
        values = [config.glyph(s.import_selected), s.name,
                  config.type_label(s.source_type), self._size_text(s),
                  getattr(s, "profile", "défaut") or "défaut"]
        for t in self.tasks:
            values.append(config.glyph(t["id"] in s.selected_task_ids))
        values.append(_DEL_GLYPH)
        return values

    def _refresh_tree(self):
        self.tree.delete(*self.tree.get_children())
        for i, s in enumerate(self.sources):
            tags = ("dup",) if self._is_indexed(s) else ()
            self.tree.insert("", "end", iid=str(i), values=self._row_values(s), tags=tags)
        self._update_total()
        self._update_heading_arrows()
        self._update_inventory_label()

    def _update_total(self):
        checked = [s for s in self.sources if s.import_selected]
        known = [s for s in checked if s.size_bytes is not None]
        total = sum(s.size_bytes for s in known)
        suffix = "" if len(known) == len(checked) else " " + i18n.t("import.partial", "(partiel)")
        txt = i18n.t(
            "import.total_summary", "{n} source(s), {c} à importer — taille cochées : {t}{suffix}",
            n=len(self.sources), c=len(checked), t=config.human_size(total), suffix=suffix)
        limit_b = self._limit_gb() * config.GB
        if limit_b > 0:
            effective = self._existing_bytes() + total
            etat = i18n.t("import.over_limit", "⚠ dépasse") if effective > limit_b \
                else i18n.t("import.under_limit", "sous")
            txt += "  •  " + i18n.t(
                "import.limit_status", "{etat} la limite ({eff} / {lim})",
                etat=etat, eff=config.human_size(effective), lim=config.human_size(limit_b))
        self.lbl_total.config(text=txt)

    # ------------------------------------------------------------------ #
    # Inventaire / dédoublonnage / volume existant                       #
    # ------------------------------------------------------------------ #
    def _inventory_matches(self) -> bool:
        """Vrai si l'inventaire (liste des sources) concerne le cas ciblé."""
        inv = self.app.inventory
        if not inv:
            return False
        case = path_parser.normalize_path(self.var_case.get()).lower()
        return bool(case) and case == inv.get("case_path_key")

    def _is_indexed(self, s) -> bool:
        if not self._inventory_matches():
            return False
        return path_parser.normalize_path(s.path).lower() in self.app.inventory["existing_paths"]

    def _existing_bytes(self) -> int:
        """Volume déjà occupé pour le garde-fou de dépassement.

        Consigne1 : on retient la **plus grande** valeur entre la taille
        autoritative du cas (``case.xml/size``) et la somme des sources lues dans
        l'inventaire — ainsi un cas dont le ``case.xml`` sous-estime le volume
        (sources listées mais pas/peu indexées) ne fausse pas le calcul.
        """
        meta = self.app.case_meta
        base = meta["size"] if meta else 0
        inv = self.app.inventory
        if inv and self._inventory_matches():
            base = max(base, inv.get("known_bytes", 0) or 0)
        return base

    def _drop_indexed(self) -> int:
        """Retire les sources déjà présentes dans le cas. Retourne le nb retiré."""
        if not self._inventory_matches():
            return 0
        before = len(self.sources)
        self.sources = [s for s in self.sources if not self._is_indexed(s)]
        return before - len(self.sources)

    def apply_inventory(self):
        """Appelé quand l'inventaire (liste des sources) vient d'être lu.

        Retire automatiquement les sources déjà indexées du récapitulatif.
        """
        removed = self._drop_indexed()
        self._refresh_tree()
        if removed:
            self.app.log.log(i18n.t(
                "import.auto_removed_log", "{n} source(s) déjà indexée(s) retirée(s) automatiquement.",
                n=removed))

    def _update_inventory_label(self):
        if not hasattr(self, "lbl_inventory"):
            return
        meta = self.app.case_meta
        if not meta:
            self.lbl_inventory.config(
                foreground="#b45309",
                text=i18n.t("import.no_case_selected",
                           "ⓘ Aucun cas sélectionné — choisissez-le dans l'onglet « 1. Inventaire du cas »."),
            )
            return
        effective = self._existing_bytes()  # max(case.xml, somme inventaire)
        txt = i18n.t("import.case_prefix", "Cas « {n} » : ", n=meta['name'])
        txt += i18n.t("import.empty", "vide") if effective == 0 else i18n.t(
            "import.already_used", "déjà {s} occupé(s)", s=config.human_size(effective))
        inv = self.app.inventory
        if not (inv and self._inventory_matches()):
            txt += "  •  " + i18n.t(
                "import.no_inventory_read",
                "⚠ liste des sources non lue (onglet 1) → pas de dédoublonnage.")
            self.lbl_inventory.config(foreground="#b45309", text=txt)
            return
        # Si la somme inventaire l'emporte sur case.xml, on le signale.
        if (inv.get("known_bytes", 0) or 0) > (meta["size"] or 0):
            txt += " " + i18n.t(
                "import.inventory_exceeds", "(somme inventaire > case.xml {s})",
                s=config.human_size(meta['size']))
        txt += "  •  " + i18n.t("import.n_indexed", "{n} source(s) indexée(s)", n=inv['source_count'])
        self.lbl_inventory.config(foreground="#16a34a" if effective == 0 else "#64748b", text=txt)

    # ------------------------------------------------------------------ #
    # Export / import de la liste du récapitulatif (JSON)                 #
    # ------------------------------------------------------------------ #
    def _export_recap(self):
        title = i18n.t("import.export_list", "Exporter la liste…")
        if not self.sources:
            messagebox.showinfo(title, i18n.t("import.recap_empty", "Le récapitulatif est vide."))
            return
        # Par défaut : dans le dossier du cas (Script\Cas\<nom>\, à côté de l'exe),
        # nom de fichier incluant le nom du cas.
        case_name = self.var_casename.get().strip() or "Case"
        safe = config.sanitize_filename(case_name)
        case_dir = config.case_dir(case_name)
        try:
            os.makedirs(case_dir, exist_ok=True)
        except OSError:
            case_dir = None
        default = f"recap_{safe}_{config.now_compact()}.json"
        path = filedialog.asksaveasfilename(
            defaultextension=".json", initialfile=default, initialdir=case_dir or None,
            filetypes=[("JSON", "*.json"), (i18n.t("common.filetype_all", "Tous"), "*.*")])
        if not path:
            return
        data = [{
            "name": s.name,
            "path": s.path,
            "source_type": s.source_type,
            "selected_task_ids": sorted(s.selected_task_ids),
            "import_selected": s.import_selected,
            "size_bytes": s.size_bytes,
            "profile": getattr(s, "profile", "défaut") or "défaut",
        } for s in self.sources]
        try:
            with open(path, "w", encoding="utf-8") as f:
                json.dump({"sources": data}, f, ensure_ascii=False, indent=2)
            self.app.log.log(i18n.t(
                "import.recap_exported_log", "Récapitulatif exporté ({n} source(s)) : {p}",
                n=len(data), p=path))
            messagebox.showinfo(title, i18n.t(
                "import.recap_exported_msg", "{n} source(s) exportée(s) :\n{p}", n=len(data), p=path))
        except OSError as exc:
            messagebox.showerror(title, i18n.t("common.export_failed", "Échec :\n{e}", e=exc))

    def _import_recap(self):
        title = i18n.t("import.import_list", "Importer une liste…")
        path = filedialog.askopenfilename(
            title=title,
            filetypes=[("JSON", "*.json"), (i18n.t("common.filetype_all", "Tous"), "*.*")])
        if not path:
            return
        try:
            with open(path, encoding="utf-8") as f:
                data = json.load(f)
        except (OSError, ValueError) as exc:
            messagebox.showerror(title, i18n.t("import.list_unreadable", "Lecture impossible :\n{e}", e=exc))
            return
        items = data.get("sources") if isinstance(data, dict) else data
        if not isinstance(items, list):
            messagebox.showerror(title, i18n.t(
                "import.list_invalid_format", "Format invalide (liste de sources attendue)."))
            return
        if self.sources and not messagebox.askyesno(
            title, i18n.t(
                "import.list_replace_confirm",
                "Remplacer le récapitulatif actuel ({cur} source(s)) par {new} source(s) du fichier ?",
                cur=len(self.sources), new=len(items))):
            return
        loaded = []
        for it in items:
            if not isinstance(it, dict) or not it.get("path"):
                continue
            loaded.append(models.Source(
                name=it.get("name") or os.path.basename(it["path"]),
                path=it["path"],
                source_type=it.get("source_type") or config.SOURCE_TYPE_FOLDER,
                selected_task_ids=set(it.get("selected_task_ids") or []),
                size_bytes=it.get("size_bytes"),
                import_selected=bool(it.get("import_selected", True)),
                profile=it.get("profile") or "défaut",
            ))
        self.sources = loaded
        self._sort_col = None
        removed = self._drop_indexed()  # dédoublonnage auto (comme « Récapituler »)
        self._refresh_tree()
        msg = i18n.t("import.list_imported_log", "Récapitulatif importé : {n} source(s) depuis {p}",
                    n=len(self.sources), p=path)
        if removed:
            msg += " " + i18n.t("import.list_imported_removed", "({n} déjà dans le cas, retirée(s)).", n=removed)
        self.app.log.log(msg)
        info = i18n.t("import.n_sources_loaded", "{n} source(s) chargée(s).", n=len(self.sources))
        if removed:
            info += "\n" + i18n.t(
                "import.n_removed_auto", "{n} déjà indexée(s) dans le cas, retirée(s) automatiquement.",
                n=removed)
        messagebox.showinfo(title, info)

    # ------------------------------------------------------------------ #
    # Interactions tableau                                               #
    # ------------------------------------------------------------------ #
    def _colid_at(self, x):
        col = self.tree.identify_column(x)  # "#k"
        try:
            idx = int(col[1:]) - 1
        except (ValueError, IndexError):
            return None
        cols = self.tree["columns"]
        return cols[idx] if 0 <= idx < len(cols) else None

    def _on_click(self, event):
        if self.tree.identify("region", event.x, event.y) != "cell":
            return
        row = self.tree.identify_row(event.y)
        colid = self._colid_at(event.x)
        if not row or not colid:
            return
        s = self.sources[int(row)]
        if colid == "import":
            s.import_selected = not s.import_selected
            self.tree.set(row, "import", config.glyph(s.import_selected))
            self._update_total()
            return
        if colid == "del":
            self.sources.pop(int(row))
            self._refresh_tree()
            self.app.log.log(i18n.t(
                "import.source_removed_log", "Source retirée du récapitulatif : {n}", n=s.name))
            return
        if colid == "profile":
            self._edit_profile(row)
            return
        if not colid.startswith("task_"):
            return
        idx = int(colid.split("_")[1])
        task_id = self.tasks[idx]["id"]
        if task_id in s.selected_task_ids:
            s.selected_task_ids.discard(task_id)
        else:
            s.selected_task_ids.add(task_id)
        self.tree.set(row, colid, config.glyph(task_id in s.selected_task_ids))

    def _on_double_click(self, event):
        if self.tree.identify("region", event.x, event.y) != "cell":
            return
        if self._colid_at(event.x) != "name":
            return
        row = self.tree.identify_row(event.y)
        if not row:
            return
        bbox = self.tree.bbox(row, "name")
        if not bbox:
            return
        x, y, w, h = bbox
        entry = ttk.Entry(self.tree)
        entry.insert(0, self.tree.set(row, "name"))
        entry.select_range(0, "end")
        entry.place(x=x, y=y, width=w, height=h)
        entry.focus_set()

        def commit(_=None):
            new = entry.get().strip()
            if new:
                self.sources[int(row)].name = new
                self.tree.set(row, "name", new)
            entry.destroy()

        entry.bind("<Return>", commit)
        entry.bind("<FocusOut>", commit)
        entry.bind("<Escape>", lambda _e: entry.destroy())

    def _edit_profile(self, row):
        """Combobox déroulant in-place pour choisir le profil d'une source."""
        s = self.sources[int(row)]
        bbox = self.tree.bbox(row, "profile")
        if not bbox:
            return
        x, y, w, h = bbox
        names = profiles.list_names()
        cb = ttk.Combobox(self.tree, values=names, state="readonly")
        current = getattr(s, "profile", profiles.DEFAULT_NAME) or profiles.DEFAULT_NAME
        cb.set(current if current in names else profiles.DEFAULT_NAME)
        cb.place(x=x, y=y, width=max(w, 140), height=h)
        cb.focus_set()

        def commit(_=None):
            val = cb.get() or profiles.DEFAULT_NAME
            s.profile = val
            self.tree.set(row, "profile", val)
            cb.destroy()

        cb.bind("<<ComboboxSelected>>", commit)
        cb.bind("<FocusOut>", lambda _e: cb.destroy())
        cb.bind("<Escape>", lambda _e: cb.destroy())

    def _refresh_default_profiles(self):
        """Alimente le combobox « Profil par défaut » avec les profils existants."""
        self.cb_default_profile["values"] = profiles.list_names()

    def _apply_profile_all(self):
        """Applique le profil choisi (combobox) à TOUTES les lignes du récap."""
        prof = self.cb_default_profile.get() or profiles.DEFAULT_NAME
        for s in self.sources:
            s.profile = prof
        self._refresh_tree()
        self.app.log.log(i18n.t(
            "import.profile_applied_all_log", "Profil « {p} » appliqué à toutes les sources ({n}).",
            p=prof, n=len(self.sources)))

    def _on_motion(self, event):
        if self.tree.identify("region", event.x, event.y) != "heading":
            self.tooltip.hide()
            return
        colid = self._colid_at(event.x)
        if colid and colid.startswith("task_"):
            idx = int(colid.split("_")[1])
            self.tooltip.show(self.tasks[idx]["name"], event.x_root + 12, event.y_root + 12)
        else:
            self.tooltip.hide()

    def _set_all(self, state):
        all_ids = {t["id"] for t in self.tasks}
        for i, s in enumerate(self.sources):
            s.selected_task_ids = set(all_ids) if state else set()
        self._refresh_tree()

    def _set_all_import(self, state):
        for s in self.sources:
            s.import_selected = state
        self._refresh_tree()

    def _toggle_column(self, task_idx, state):
        if not (0 <= task_idx < len(self.tasks)):
            return
        task_id = self.tasks[task_idx]["id"]
        colid = self._task_colid(task_idx)
        for i, s in enumerate(self.sources):
            if state:
                s.selected_task_ids.add(task_id)
            else:
                s.selected_task_ids.discard(task_id)
            if self.tree.exists(str(i)):
                self.tree.set(str(i), colid, config.glyph(state))

    # ------------------------------------------------------------------ #
    # Tri                                                                #
    # ------------------------------------------------------------------ #
    def _sort_key(self, colid):
        if colid == "import":
            return lambda s: 0 if s.import_selected else 1
        if colid == "del":
            return lambda s: 0  # pas de tri pertinent sur la croix
        if colid == "name":
            return lambda s: s.name.lower()
        if colid == "type":
            return lambda s: config.type_label(s.source_type)
        if colid == "size":
            return lambda s: s.size_bytes if s.size_bytes is not None else -1
        if colid == "profile":
            return lambda s: (getattr(s, "profile", "") or "").lower()
        if colid.startswith("task_"):
            tid = self.tasks[int(colid.split("_")[1])]["id"]
            return lambda s: 1 if tid in s.selected_task_ids else 0
        return lambda s: ""

    def _sort_by(self, colid):
        self._sort_asc = not self._sort_asc if self._sort_col == colid else True
        self._sort_col = colid
        self.sources.sort(key=self._sort_key(colid), reverse=not self._sort_asc)
        self._refresh_tree()

    def _update_heading_arrows(self):
        for colid, base in self._heading_base.items():
            arrow = ""
            if colid == self._sort_col:
                arrow = " ▲" if self._sort_asc else " ▼"
            self.tree.heading(colid, text=base + arrow)

    # ------------------------------------------------------------------ #
    # Calcul de taille (thread)                                          #
    # ------------------------------------------------------------------ #
    def calculer_taille(self):
        checked = [s for s in self.sources if s.import_selected]
        if not checked:
            messagebox.showinfo(
                i18n.t("import.size_title", "Taille"),
                i18n.t("import.no_checked",
                      "Aucune source cochée « Importer ».\nSeules les lignes cochées sont mesurées."))
            return
        self.app.log.log(i18n.t(
            "import.computing_size_log", "Calcul de la taille de {n} source(s) cochée(s)…", n=len(checked)))
        threading.Thread(target=self._size_worker, daemon=True).start()

    def _size_worker(self):
        snapshot = [s for s in self.sources if s.import_selected]
        meta = self.app.case_meta
        # Réutilise les tailles déjà mesurées (cache IF_<cas>.info, par chemin) :
        # évite de rescanner une source déjà mesurée lors d'une session précédente.
        cache = case_info.get_folder_sizes(meta["folder"], meta["name"]) if meta else {}
        to_persist = {}
        for s in snapshot:
            cached = cache.get(path_parser.normalize_path(s.path).lower())
            if cached is not None:
                s.size_bytes = int(cached)
            else:
                s.size_bytes = sizing.source_size(s)
                to_persist[s.path] = s.size_bytes
        if meta and to_persist:
            case_info.update_folder_sizes(meta["folder"], meta["name"], to_persist)
        reused = len(snapshot) - len(to_persist)
        if reused:
            self.app.log.log(i18n.t(
                "import.size_cache_reused_log",
                "{n} source(s) déjà mesurée(s) reprise(s) du cache (IF_<cas>.info).", n=reused))
        self.after(0, self._size_done)

    def _size_done(self):
        for i, s in enumerate(self.sources):
            if self.tree.exists(str(i)):
                self.tree.set(str(i), "size", self._size_text(s))
        self._update_total()
        total = sum((s.size_bytes or 0) for s in self.sources if s.import_selected)
        self.app.log.log(i18n.t(
            "import.size_done_log", "Calcul des tailles terminé. Total cochées : {t}.",
            t=config.human_size(total)))

    # ------------------------------------------------------------------ #
    # Génération                                                         #
    # ------------------------------------------------------------------ #
    def _limit_gb(self) -> float:
        """Limite par cas en Go (float : autorise les valeurs fractionnaires).

        Auparavant tronquée par ``int()`` → toute limite < 1 Go (ex. 0.260)
        tombait à 0 et était interprétée comme « pas de limite ». On accepte la
        virgule décimale FR (« 0,260 ») aussi bien que le point.
        """
        try:
            raw = (self.var_limit.get() or "").strip().replace(",", ".")
            return max(0.0, float(raw))
        except (ValueError, TypeError):
            return float(config.DEFAULT_SIZE_LIMIT_GB)

    def _params(self):
        case_name = self.var_casename.get().strip()
        names = {getattr(s, "profile", "défaut") or "défaut" for s in self.sources}
        return {
            "user": self.app.var_user.get().strip(),
            "exe": path_parser.clean_field(self.app.var_exe.get()),
            "case": path_parser.clean_field(self.var_case.get()),
            "casename": case_name,
            "tasks": path_parser.clean_field(self.var_tasks.get()),
            "output": config.case_scripts_dir(case_name or "Case"),
            "tz": self.var_tz.get().strip() or config.DEFAULT_TIMEZONE,
            "extra": self.var_extra.get(),
            "limit_gb": self._limit_gb(),
            "existing_bytes": self._existing_bytes(),
            "profile_options": profiles.emit_map(names),
        }

    def persist(self, settings):
        settings.set("last_case", self.var_case.get())
        settings.set("casename", self.var_casename.get())
        settings.set("tasks_path", self.var_tasks.get())
        settings.set("timezone", self.var_tz.get())
        settings.set("limit_gb", str(self._limit_gb()))
        settings.set("extra", self.var_extra.get())

    @staticmethod
    def _format_list(items, cap=15):
        text = "\n".join("• " + i for i in items[:cap])
        if len(items) > cap:
            text += "\n" + i18n.t("import.and_n_more", "… et {n} autre(s).", n=len(items) - cap)
        return text

    def generer(self):
        params = self._params()
        if not self.app.case_meta:
            messagebox.showerror(
                i18n.t("common.case_required_title", "Cas requis"),
                i18n.t("import.select_case_target",
                      "Sélectionnez d'abord un cas dans l'onglet « 1. Inventaire du cas »."))
            return
        # Seules les lignes cochées « Importer » sont générées.
        selected = [s for s in self.sources if s.import_selected]
        if not selected:
            messagebox.showerror(
                i18n.t("import.empty_selection_title", "Sélection vide"),
                i18n.t("import.empty_selection_body",
                      "Cochez au moins une source dans la colonne « Imp. » (Importer)."))
            return
        # Anomalie corrigée (champ « Fichier de tâches » vidé en cours de session) :
        #   • aucune tâche cochée → on n'exige aucun fichier ;
        #   • fichier toujours valide → on le relit (prend en compte une édition) ;
        #   • champ vidé / fichier disparu MAIS définitions déjà en mémoire → on
        #     génère avec ``self.tasks`` (build_combo_files travaille dessus, pas
        #     sur le fichier) ;
        #   • rien en mémoire et pas de fichier lisible → erreur claire.
        wants_tasks = any(s.selected_task_ids for s in selected)
        if not wants_tasks:
            tasks_loaded = True
        elif self._tasks_from_case and self.tasks:
            tasks_loaded = True  # tâches recyclées de l'inventaire : pas de fichier
        else:
            tasks_path = path_parser.clean_field(self.var_tasks.get())
            if tasks_path and os.path.isfile(tasks_path):
                tasks_loaded = self._load_tasks(show_error=True)
            elif self.tasks:
                tasks_loaded = True
                self.app.log.log(i18n.t(
                    "import.tasks_file_unavailable_log",
                    "Fichier de tâches indisponible (champ vidé ou fichier absent) : "
                    "utilisation des définitions déjà chargées en mémoire."))
            else:
                tasks_loaded = self._load_tasks(show_error=True)

        errors, warnings = validation.collect(selected, params, tasks_loaded)
        if errors:
            messagebox.showerror(
                i18n.t("import.corrections_needed", "Corrections nécessaires"),
                self._format_list(errors, 30))
            return

        limit_b = self._limit_gb() * config.GB
        if limit_b > 0 and any(s.size_bytes is None for s in selected):
            self.app.log.log(i18n.t(
                "import.computing_missing_sizes_log",
                "Calcul des tailles manquantes (sources cochées) avant génération…"))
            for s in selected:
                if s.size_bytes is None:
                    s.size_bytes = sizing.source_size(s)
            self._refresh_tree()

        # Dépassement : on décoche le surplus (séquentiellement) pour montrer ce qui
        # tient, on AVERTIT, et on s'ARRÊTE — pas de génération. L'utilisateur ajuste
        # librement les coches puis relance « Générer » quand la sélection lui convient.
        dropped = self._enforce_limit(selected, params["existing_bytes"], limit_b)
        if dropped:
            self._refresh_tree()
            vol = sum((s.size_bytes or 0) for s in dropped)
            self.app.log.log(i18n.t(
                "import.limit_exceeded_log",
                "Dépassement limite : {n} source(s) décochée(s) ({v}). "
                "Génération suspendue — ajustez les coches puis relancez « Générer ».",
                n=len(dropped), v=config.human_size(vol)))
            messagebox.showwarning(
                i18n.t("import.limit_exceeded_title", "Limite atteinte — génération suspendue"),
                i18n.t(
                    "import.limit_exceeded_body",
                    "La limite de {lim:g} Go serait dépassée.\n\n"
                    "{n} source(s) ({v}) ont été DÉCOCHÉES (la partie qui tient reste cochée) :\n"
                    "{list}\n\nRien n'a été généré. Vérifiez / ajustez les coches « Imp. », "
                    "puis relancez « Générer » pour importer ce que vous gardez.\n\n"
                    "Pour le reste : créez le sous-cas manuellement dans Intella, "
                    "ciblez-le comme cas, recochez et réimportez.",
                    lim=self._limit_gb(), n=len(dropped), v=config.human_size(vol),
                    list=self._format_list([s.name for s in dropped], 12)))
            return

        if warnings and not messagebox.askyesno(
            i18n.t("import.warnings_title", "Avertissements"),
            self._format_list(warnings) + "\n\n" + i18n.t(
                "import.generate_anyway", "Générer malgré tout ?")
        ):
            return

        try:
            report = generator.generate(selected, params, self.tasks, self.app.log.log)
        except OSError as exc:
            messagebox.showerror(i18n.t("import.write_title", "Écriture"),
                                 i18n.t("common.export_failed", "Échec :\n{e}", e=exc))
            return

        self.app.save_settings()
        self._show_report(report, len(selected))

    def _enforce_limit(self, selected, existing_bytes, limit_bytes) -> list:
        """Décoche le surplus pour tenir sous la limite (coupe séquentielle).

        Parcourt ``selected`` dans l'ordre ; dès qu'une source ferait dépasser la
        limite, elle et toutes les suivantes sont décochées (``import_selected``
        = False) → coupe nette : haut = cas principal, bas = sous-cas manuel.
        Retourne la liste des sources décochées.
        """
        if limit_bytes <= 0:
            return []
        acc = max(0, int(existing_bytes or 0))
        dropped, overflow = [], False
        for s in selected:
            if overflow:
                s.import_selected = False
                dropped.append(s)
                continue
            size = s.size_bytes or 0
            if acc + size > limit_bytes:
                overflow = True
                s.import_selected = False
                dropped.append(s)
            else:
                acc += size
        return dropped

    def _show_report(self, report, n_sources):
        out = os.path.abspath(report["output"])
        existing = report.get("existing", 0)
        effective = report.get("effective", report["total"])
        lines = [i18n.t("import.report_done", "Génération terminée — {n} source(s) importée(s).",
                       n=n_sources),
                 i18n.t("import.report_new_volume", "Volume des nouvelles sources : {v}.",
                       v=config.human_size(report['total']))]
        if existing:
            lines.append(i18n.t(
                "import.report_existing", "Déjà dans le cas : {e}  →  total {t}.",
                e=config.human_size(existing), t=config.human_size(effective)))
        lines.append("")
        if report.get("over_limit"):
            lines.append(i18n.t(
                "import.report_over_limit", "⚠ Le total dépasse la limite de {lim:g} Go de {ov}.",
                lim=self._limit_gb(), ov=config.human_size(report.get('overflow', 0))))
            lines.append(i18n.t(
                "import.report_no_subcase",
                "Aucun sous-cas n'est créé automatiquement : créez-le "
                "manuellement dans Intella puis réimportez le reste."))
        else:
            lines.append(i18n.t("import.report_single_case", "Un seul cas (sous la limite)."))
        if report["oversized"]:
            names = ", ".join(s.name for s in report["oversized"])
            lines.append("")
            lines.append(i18n.t(
                "import.report_oversized",
                "⚠ Source(s) seule(s) > limite (non fractionnable) : {n}", n=names))
        lines.append("")
        lines.append(i18n.t(
            "import.report_resilient", "Import résilient : 1 commande par source, log par source."))
        run_id = report.get("run_id")
        if run_id:
            lines.append(i18n.t(
                "import.report_run_logs",
                "Logs de ce run : logs\\{r}\\ (« Valider les opérations » lira ce run).", r=run_id))
        lines.append(i18n.t("import.report_folder", "Dossier : {d}", d=out))
        lines.append(i18n.t("import.report_open_folder", "Ouvrir le dossier des scripts ?"))

        if messagebox.askyesno(i18n.t("import.report_title", "Terminé"), "\n".join(lines)):
            try:
                os.startfile(out)  # Windows
            except OSError:
                pass

    # ------------------------------------------------------------------ #
    # Importer : exécuter le .bat généré                                 #
    # ------------------------------------------------------------------ #
    def _main_bat_path(self):
        """Chemin du .bat d'import du cas courant (``<cas>_import.bat``), ou ``None``."""
        name = self.var_casename.get().strip() or "Case"
        scripts = config.case_scripts_dir(name)
        safe = config.sanitize_filename(name)
        single = os.path.join(scripts, f"{safe}_import.bat")
        return single if os.path.isfile(single) else None

    def importer(self):
        title = i18n.t("import.run_import", "Importer (lancer le .bat)")
        if not self.app.case_meta:
            messagebox.showinfo(title, i18n.t(
                "import.select_case_short", "Sélectionnez d'abord un cas (onglet « 1. Inventaire du cas »)."))
            return
        bat = self._main_bat_path()
        if not bat:
            messagebox.showwarning(title, i18n.t(
                "import.no_bat_found",
                "Aucun fichier d'import trouvé pour ce cas.\n"
                "Cliquez d'abord sur « Générer les fichiers d'import »."))
            return
        if not messagebox.askyesno(
            title, i18n.t(
                "import.run_confirm",
                "Lancer l'import dans Intella ?\n\n{b}\n\n"
                "IntellaCmd va ajouter les sources au cas (action non réversible "
                "côté cas). Une fenêtre de console s'ouvre et affiche la progression.\n\n"
                "Continuer ?", b=os.path.basename(bat))):
            return
        try:
            os.startfile(bat)  # Windows : exécute le .bat dans une console
            self.app.log.log(i18n.t("import.launched_log", "Import lancé : {b}", b=bat))
        except OSError as exc:
            self.app.log.log(i18n.t(
                "import.launch_failed_log", "Échec du lancement de l'import : {e}", e=exc), level="ERROR")
            messagebox.showerror(title, i18n.t("import.launch_impossible", "Lancement impossible :\n{e}", e=exc))

    # ------------------------------------------------------------------ #
    # Validation des opérations (re-scan du cas + analyse des logs)      #
    # ------------------------------------------------------------------ #
    def valider_operations(self):
        title = i18n.t("import.validate", "Valider les opérations")
        meta = self.app.case_meta
        if not meta:
            messagebox.showinfo(title, i18n.t(
                "import.select_case_short", "Sélectionnez d'abord un cas (onglet « 1. Inventaire du cas »)."))
            return
        exe = path_parser.clean_field(self.app.var_exe.get())
        user = self.app.var_user.get().strip()
        if not exe or not user:
            messagebox.showerror(title, i18n.t(
                "import.validate_requires", "IntellaCmd.exe et l'utilisateur sont requis."))
            return
        logs_dir = config.case_logs_dir(meta["name"])
        self.btn_validate.config(state="disabled")
        self.app.log.log(i18n.t(
            "import.validate_start_log", "Validation des opérations : re-scan du cas + analyse des logs…"))
        threading.Thread(target=self._validate_worker,
                         args=(exe, user, meta["folder"], logs_dir), daemon=True).start()

    def _validate_worker(self, exe, user, case, logs_dir):
        try:
            _rows, _cols, inventory = case_export.run_export_source_list(
                exe, user, case, self.app.log.log,
                extra_args="-autoSelectFullProcessingLicense")
            # Analyse le run le plus récent (sous-dossier horodaté), ou l'ancien
            # format plat si aucun sous-dossier de run n'existe.
            run_dir = op_validation.latest_run_dir(logs_dir)
            logs = op_validation.scan_logs(run_dir)
            self.after(0, self._validate_done, inventory, logs, run_dir)
        except Exception as exc:
            self.after(0, self._validate_error, str(exc))

    def _validate_error(self, msg):
        self.btn_validate.config(state="normal")
        self.app.log.log(i18n.t("import.validate_rescan_failed_log", "Validation : échec du re-scan : {m}", m=msg),
                         level="ERROR")
        messagebox.showerror(i18n.t("import.validate", "Valider les opérations"), msg)

    def _validate_done(self, inventory, logs, run_dir=None):
        self.btn_validate.config(state="normal")
        existing = inventory["existing_paths"]
        # Index logs par chemin d'évidence (normalisé) pour le recoupement.
        log_by_path = {}
        for lg in logs:
            ev = lg.get("evidence")
            if ev:
                log_by_path[path_parser.normalize_path(ev).lower()] = lg

        rows = []
        if self.sources:
            for s in self.sources:
                key = path_parser.normalize_path(s.path).lower()
                in_case = key in existing
                lg = log_by_path.get(key)
                rows.append((s.name, in_case, lg))
        else:
            # Pas de récap en mémoire : on se base sur les logs trouvés.
            for lg in logs:
                ev = lg.get("evidence") or ""
                key = path_parser.normalize_path(ev).lower() if ev else ""
                in_case = key in existing if key else False
                rows.append((lg["file"], in_case, lg))

        run_txt = ""
        if run_dir and op_validation._RUN_RE.match(os.path.basename(run_dir)):
            run_txt = i18n.t("import.validate_run_suffix", " (run {r})", r=os.path.basename(run_dir))
        self.app.log.log(i18n.t(
            "import.validate_summary_log",
            "Validation{r} : {n} source(s) dans le cas, {l} log(s) analysé(s).",
            r=run_txt, n=inventory['source_count'], l=len(logs)))
        # Résumé par source dans le Journal (OK / cause d'échec).
        for name, in_case, lg in rows:
            if in_case and (lg is None or lg["ok"]):
                self.app.log.log(i18n.t("import.validate_present", "  ✔ {n} : présente dans le cas.", n=name))
            elif lg is not None and not lg["ok"]:
                self.app.log.log(i18n.t(
                    "import.validate_failed", "  ✗ {n} : échec — {m}", n=name, m=lg['message']),
                    level="ERROR")
            elif not in_case:
                self.app.log.log(i18n.t(
                    "import.validate_absent",
                    "  ✗ {n} : absente du cas (aucun log d'import correspondant).", n=name),
                    level="ERROR")
            else:
                self.app.log.log(i18n.t("import.validate_other", "  • {n} : {m}", n=name, m=lg['message']))
        self._show_validation(inventory, logs, rows, run_dir)

    def _show_validation(self, inventory, logs, rows, run_dir=None):
        win = tk.Toplevel(self)
        win.title(i18n.t("import.validate", "Valider les opérations"))
        win.geometry("900x460")

        n_ok = sum(1 for _n, in_case, _lg in rows if in_case)
        run_txt = ""
        if run_dir and op_validation._RUN_RE.match(os.path.basename(run_dir)):
            run_txt = i18n.t("import.validate_run_analyzed", "  Run analysé : {r}.", r=os.path.basename(run_dir))
        head = ttk.Label(
            win, padding=8,
            text=i18n.t(
                "import.validate_head",
                "Cas « {c} » : {n} source(s) présente(s).  Sur {v} vérifiée(s) : {ok} dans le cas, "
                "{ko} absente(s).  {l} log(s) analysé(s).",
                c=inventory['case_name'], n=inventory['source_count'], v=len(rows),
                ok=n_ok, ko=len(rows) - n_ok, l=len(logs)) + run_txt)
        head.pack(fill="x")

        holder = ttk.Frame(win)
        holder.pack(fill="both", expand=True, padx=8, pady=(0, 8))
        cols = ("source", "case", "log")
        tree = ttk.Treeview(holder, columns=cols, show="headings", selectmode="browse")
        tree.heading("source", text=i18n.t("import.col_source", "Source"))
        tree.heading("case", text=i18n.t("import.col_in_case", "Dans le cas"))
        tree.heading("log", text=i18n.t("import.col_import_log", "Log d'import"))
        tree.column("source", width=300, anchor="w", stretch=False)
        tree.column("case", width=90, anchor="center", stretch=False)
        tree.column("log", width=460, anchor="w", stretch=False)
        vsb = ttk.Scrollbar(holder, orient="vertical", command=tree.yview)
        hsb = ttk.Scrollbar(holder, orient="horizontal", command=tree.xview)
        tree.configure(yscrollcommand=vsb.set, xscrollcommand=hsb.set)
        tree.grid(row=0, column=0, sticky="nsew")
        vsb.grid(row=0, column=1, sticky="ns")
        hsb.grid(row=1, column=0, sticky="ew")
        holder.rowconfigure(0, weight=1)
        holder.columnconfigure(0, weight=1)
        tree.tag_configure("ok", background="#dcfce7")
        tree.tag_configure("ko", background="#ffd9d9")

        export_rows = []  # lignes (Source, Dans le cas, Log) pour l'export CSV
        ok_label = i18n.t("import.log_ok", "OK")
        ko_label = i18n.t("import.log_failed", "ÉCHEC : {m}")
        for name, in_case, lg in rows:
            if lg is None:
                log_txt = "—"
            elif lg["ok"] and not lg["message"]:
                log_txt = ok_label
            elif lg["ok"]:
                log_txt = lg["message"]
            else:
                log_txt = ko_label.format(m=lg["message"])
            tag = "ok" if in_case else "ko"
            case_txt = "✓" if in_case else "✗"
            tree.insert("", "end", values=(name, case_txt, log_txt), tags=(tag,))
            export_rows.append((name, i18n.t("common.yes", "oui") if in_case else i18n.t("common.no", "non"),
                               log_txt))

        bar = ttk.Frame(win)
        bar.pack(fill="x", pady=(0, 8))
        make_button(bar, i18n.t("import.close", "Fermer"), win.destroy).pack(side="right", padx=8)
        make_button(bar, i18n.t("common.export_csv", "Exporter en CSV…"),
                    lambda: self._export_validation(export_rows)).pack(side="right")

    def _export_validation(self, export_rows):
        """Exporte le résultat de la validation (Source / Dans le cas / Log) en CSV."""
        title = i18n.t("common.export_title", "Export")
        if not export_rows:
            messagebox.showinfo(title, i18n.t("import.no_rows_to_export", "Aucune ligne à exporter."))
            return
        meta = self.app.case_meta
        case_part = config.sanitize_filename(meta["name"]) + "_" if meta else ""
        default = f"validation_{case_part}{config.now_compact()}.csv"
        path = filedialog.asksaveasfilename(
            defaultextension=".csv", initialfile=default,
            filetypes=[("CSV", "*.csv"), (i18n.t("common.filetype_all", "Tous"), "*.*")],
        )
        if not path:
            return
        try:
            with open(path, "w", newline="", encoding="utf-8-sig") as f:
                writer = csv.writer(f)
                writer.writerow([i18n.t("import.col_source", "Source"),
                                 i18n.t("import.col_in_case", "Dans le cas"),
                                 i18n.t("import.col_import_log", "Log d'import")])
                writer.writerows(export_rows)
            self.app.log.log(i18n.t("import.validation_exported_log", "Validation exportée en CSV : {p}", p=path))
            messagebox.showinfo(title, i18n.t("common.exported_to", "Exporté :\n{p}", p=path))
        except OSError as exc:
            messagebox.showerror(title, i18n.t("common.export_failed", "Échec :\n{e}", e=exc))
