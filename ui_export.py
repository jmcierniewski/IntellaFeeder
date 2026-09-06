"""Onglet « 1. Inventaire du cas ».

Première étape du workflow :
1. Sélection du dossier de cas → détection de ``case.xml`` (validation + récup du
   nom/utilisateur/taille, publiés sur ``app.case_meta`` ; alimente l'onglet Détail
   et verrouille le cas dans l'onglet Import).
2. « Lire les sources » → ``-exportSourceList`` (IntellaCmd) : liste des sources
   déjà indexées (dédoublonnage) ; publié sur ``app.inventory``.
3. « Scanner les dossiers à 0 » → mesure facultative des sources « dossier » dont
   la taille n'est pas reportée par Intella.
"""

import json
import os
import queue
import shutil
import threading
import tkinter as tk
from tkinter import filedialog, messagebox, ttk

import case_export
import case_info
import case_meta
import config
import i18n
import path_parser
import profile_translate
import sizing
from ui_widgets import MeasureBar, make_button

# En-têtes affichés du tableau (les clés internes des lignes restent en
# français partout dans le code — ``case_export``, CSV… — pour ne rien casser ;
# seul le libellé visible à l'écran est traduit).
_COLUMN_LABEL_KEYS = {
    "Nom": "col.name", "Type": "col.type", "Fuseau": "col.timezone",
    "Taille": "col.size", "Octets": "col.bytes", "Segments": "col.segments",
    "Chemin": "col.path", "Tâches": "col.tasks",
    "Sous-cas": "col.subcase",
}


class ExportTab(ttk.Frame):
    # Écart relatif toléré entre la taille du cas (case.xml) et la somme des
    # sources lues, au-delà duquel on alerte (Consigne1).
    SIZE_TOLERANCE = 0.02

    def __init__(self, parent, app):
        super().__init__(parent)
        self.app = app
        self.rows: list[dict] = []
        self.columns: list[str] = []
        # Colonnes du CSV : suivent le type de cas lu (cf. _done).
        self.csv_columns: list[str] = list(case_export.CSV_COLUMNS)
        self._scan_running = False   # scan des dossiers à 0 en cours
        self._scan_cancel = False    # annulation demandée (lue par le worker)

        top = ttk.LabelFrame(self, text=i18n.t("inventory.case_frame", "Cas à inventorier"))
        top.pack(fill="x", padx=8, pady=8)
        top.columnconfigure(1, weight=1)

        self.var_case = tk.StringVar(value=app.settings.get("last_case"))
        ttk.Label(top, text=i18n.t("inventory.case_folder", "Dossier du cas")).grid(
            row=0, column=0, sticky="w", padx=6, pady=4)
        ent = ttk.Entry(top, textvariable=self.var_case)
        ent.grid(row=0, column=1, sticky="ew", padx=6, pady=4)
        ent.bind("<FocusOut>", lambda _e: self._detect_case())
        ent.bind("<Return>", lambda _e: self._detect_case())
        make_button(top, i18n.t("common.browse", "Parcourir…"), self._pick_case).grid(
            row=0, column=2, padx=6, pady=4)

        # Licence : sans cet argument, IntellaCmd réclame une sélection
        # interactive et n'écrit aucun XML (cause du « fichier non créé »).
        self.var_autolicense = tk.BooleanVar(value=True)
        ttk.Checkbutton(
            top, variable=self.var_autolicense,
            text=i18n.t("inventory.autolicense",
                       "Sélection auto de licence (-autoSelectFullProcessingLicense)"),
        ).grid(row=1, column=1, sticky="w", padx=6, pady=2)

        self.var_extra = tk.StringVar(value=app.settings.get("export_extra"))
        ttk.Label(top, text=i18n.t("common.extra_args", "Arguments suppl.")).grid(
            row=2, column=0, sticky="w", padx=6, pady=4)
        ttk.Entry(top, textvariable=self.var_extra).grid(row=2, column=1, sticky="ew", padx=6, pady=4)

        # Tous les boutons d'action ont la même apparence (tk.Button classique,
        # comme « Scanner les dossiers à 0 ») ; seule la couleur peut différer.
        actions = ttk.Frame(top)
        actions.grid(row=3, column=1, columnspan=2, sticky="w", padx=6, pady=4)
        self.btn_run = self._mk_btn(actions, i18n.t("inventory.run", "Lire les sources (IntellaCmd)"),
                                    self._run)
        self.btn_run.pack(side="left")
        self.btn_scan = self._mk_btn(actions, i18n.t("inventory.scan", "Scanner les dossiers à 0"),
                                     self._scan_zero)
        self.btn_scan.pack(side="left", padx=6)
        self._scan_btn_default = {
            "bg": self.btn_scan.cget("bg"), "fg": self.btn_scan.cget("fg"),
            "activebackground": self.btn_scan.cget("activebackground"),
            "activeforeground": self.btn_scan.cget("activeforeground"),
        }
        self._mk_btn(actions, i18n.t("common.export_csv", "Exporter en CSV…"),
                    self._export_csv).pack(side="left")
        self.btn_export_xml = self._mk_btn(actions, i18n.t("inventory.export_xml", "Exporter le XML…"),
                                           self._export_xml)
        self.btn_export_xml.pack(side="left", padx=6)
        # « Exporter les tâches du cas » : recyclage des tâches de l'inventaire
        # (placé ici, à gauche d'« Info Profil », car il dépend de l'inventaire lu).
        self._mk_btn(actions, i18n.t("inventory.export_tasks", "Exporter les tâches du cas…"),
                    self._export_case_tasks).pack(side="left")
        # « Info Profil » : couleur de l'onglet Profils (violet) pour le rattacher
        # visuellement (réglages de la source sélectionnée → onglet Profils).
        self._mk_btn(actions, i18n.t("inventory.info_profile", "Info Profil →"), self._info_profile,
                     color=config.PROFILE_TAB_COLOR).pack(side="left", padx=6)

        # Bandeau de progression du scan des dossiers à 0 (masqué au repos) :
        # même widget que l'onglet Import (progression + annulation).
        self.scan_bar = MeasureBar(self, pack_opts={"fill": "x", "padx": 12, "pady": (0, 4)})

        self.lbl_summary = ttk.Label(self, text=i18n.t("inventory.no_case", "Aucun cas sélectionné."))
        self.lbl_summary.pack(anchor="w", padx=12, pady=(0, 4))

        holder = ttk.Frame(self)
        holder.pack(fill="both", expand=True, padx=8, pady=(0, 8))
        self.tree = ttk.Treeview(holder, show="headings", selectmode="browse")
        vsb = ttk.Scrollbar(holder, orient="vertical", command=self.tree.yview)
        hsb = ttk.Scrollbar(holder, orient="horizontal", command=self.tree.xview)
        self.tree.configure(yscrollcommand=vsb.set, xscrollcommand=hsb.set)
        self.tree.grid(row=0, column=0, sticky="nsew")
        vsb.grid(row=0, column=1, sticky="ns")
        hsb.grid(row=1, column=0, sticky="ew")
        holder.rowconfigure(0, weight=1)
        holder.columnconfigure(0, weight=1)

        if case_meta.has_case_xml(path_parser.clean_field(self.var_case.get())):
            self._detect_case()

    @staticmethod
    def _mk_btn(parent, text, command, **kw):
        """Bouton d'action à l'apparence unifiée de l'application."""
        return make_button(parent, text, command, **kw)

    # ------------------------------------------------------------------ #
    # Détection du dossier de cas (case.xml)                             #
    # ------------------------------------------------------------------ #
    def _pick_case(self):
        current = path_parser.clean_field(self.var_case.get())
        initial = current if current and os.path.isdir(current) else None
        d = filedialog.askdirectory(
            title=i18n.t("inventory.pick_case_title", "Dossier du cas Intella"), initialdir=initial)
        if d:
            self.var_case.set(os.path.normpath(d))
            self._detect_case()

    def _detect_case(self):
        case = path_parser.clean_field(self.var_case.get())
        if not case:
            self.app.clear_case_meta()
            self.lbl_summary.config(text=i18n.t("inventory.no_case", "Aucun cas sélectionné."))
            return
        if self.app.case_meta and self.app.case_meta["folder"] == case:
            return  # déjà détecté, évite les doublons sur FocusOut
        try:
            meta = case_meta.read_case(case)
        except FileNotFoundError as exc:
            self.app.clear_case_meta()
            self.lbl_summary.config(text=i18n.t(
                "inventory.not_a_case", "⚠ Pas un dossier de cas Intella (case.xml absent)."))
            messagebox.showwarning(i18n.t("inventory.case_folder_title", "Dossier de cas"), str(exc))
            return
        except Exception as exc:  # XML illisible…
            self.app.clear_case_meta()
            self.lbl_summary.config(text=i18n.t("inventory.xml_unreadable", "⚠ case.xml illisible."))
            messagebox.showerror(
                i18n.t("inventory.case_folder_title", "Dossier de cas"),
                i18n.t("inventory.xml_read_failed", "Lecture de case.xml impossible :\n{e}", e=exc))
            return
        self.app.set_case_meta(meta)
        self.app.log.log(i18n.t(
            "inventory.case_detected_log",
            "Cas détecté : « {n} » — créé par {u}, {s} occupé(s).",
            n=meta['name'], u=meta['user'], s=config.human_size(meta['size'])))
        if meta.get("is_compound"):
            self._announce_compound(meta)
            return
        self.lbl_summary.config(text=i18n.t(
            "inventory.case_detected_summary",
            "Cas « {n} » — {s} occupé(s). « Lire les sources » pour le dédoublonnage.",
            n=meta['name'], s=config.human_size(meta['size'])))

    def _announce_compound(self, meta):
        """Cas compound : dire ce qu'il est et pourquoi l'Import est fermé.

        Le compound ne contient aucune source en propre ; il référence des
        sous-cas et porte la taille TOTALE de l'ensemble. Les sources se lisent
        sous-cas par sous-cas (« Lire les sources » s'en charge).
        """
        subs = meta.get("subcases", [])
        missing = [sc for sc in subs if not sc.get("exists")]
        txt = i18n.t(
            "inventory.compound_summary",
            "Cas COMPOUND « {n} » — {c} sous-cas, {s} au total. Aucune source en propre : "
            "l'onglet Import est désactivé (ajoutez les sources dans un sous-cas).",
            n=meta['name'], c=len(subs), s=config.human_size(meta['size']))
        if missing:
            txt += "  •  " + i18n.t(
                "inventory.compound_missing",
                "{n} sous-cas inaccessible(s) depuis ce poste", n=len(missing))
        self.lbl_summary.config(text=txt)
        self.app.log.log(i18n.t(
            "inventory.compound_log",
            "Cas compound : {c} sous-cas déclaré(s), {m} inaccessible(s).",
            c=len(subs), m=len(missing)),
            level="WARN" if missing else "INFO")

    # ------------------------------------------------------------------ #
    def _extra_args(self) -> str:
        parts = []
        if self.var_autolicense.get():
            parts.append("-autoSelectFullProcessingLicense")
        free = self.var_extra.get().strip()
        if free:
            parts.append(free)
        return " ".join(parts)

    def _run(self):
        if not self.app.case_meta:
            messagebox.showerror(
                i18n.t("common.case_required_title", "Cas requis"),
                i18n.t("inventory.case_required_body",
                      "Sélectionnez d'abord un dossier de cas valide (case.xml détecté)."))
            return
        exe = path_parser.clean_field(self.app.var_exe.get())
        user = self.app.var_user.get().strip()
        case = self.app.case_meta["folder"]
        if not exe:
            messagebox.showerror(i18n.t("common.fields_required_title", "Champs requis"),
                                 i18n.t("inventory.exe_required", "Renseignez IntellaCmd.exe (en haut)."))
            return
        if not user:
            messagebox.showerror(i18n.t("common.fields_required_title", "Champs requis"),
                                 i18n.t("inventory.user_required", "Utilisateur introuvable dans case.xml."))
            return
        self.app.settings.set("export_extra", self.var_extra.get())
        self.btn_run.config(state="disabled")
        self.lbl_summary.config(text=i18n.t("inventory.reading", "Lecture en cours…"))
        self.app.log.log(i18n.t("inventory.reading_log", "Inventaire des sources du cas : {c}", c=case))
        threading.Thread(target=self._worker, args=(exe, user, case), daemon=True).start()

    def _worker(self, exe, user, case):
        try:
            meta = self.app.case_meta or {}
            if meta.get("is_compound"):
                # Un compound n'a pas de source en propre : on interroge chacun
                # de ses sous-cas et on concatène (colonne « Sous-cas »).
                rows, columns, inventory = case_export.run_export_subcases(
                    exe, user, meta.get("subcases", []), self.app.log.log,
                    extra_args=self._extra_args(),
                    case_name=meta.get("name", ""), case_path=case,
                )
            else:
                rows, columns, inventory = case_export.run_export_source_list(
                    exe, user, case, self.app.log.log, extra_args=self._extra_args()
                )
            self.after(0, self._done, rows, columns, inventory)
        except Exception as exc:  # FileNotFound, RuntimeError, parse…
            self.after(0, self._error, str(exc))

    def _error(self, msg):
        self.btn_run.config(state="normal")
        self.lbl_summary.config(text=i18n.t("inventory.read_failed", "Échec de la lecture (voir Journal)."))
        self.app.log.log(i18n.t("inventory.read_error_log", "Erreur inventaire : {m}", m=msg), level="ERROR")
        messagebox.showerror(i18n.t("inventory.sources_title", "Inventaire des sources"), msg)

    def _done(self, rows, columns, inventory):
        self.btn_run.config(state="normal")
        self.rows, self.columns = rows, columns
        self.csv_columns = list(case_export.CSV_COLUMNS_COMPOUND
                                if inventory.get("is_compound")
                                else case_export.CSV_COLUMNS)
        self.app.inventory = inventory
        # Réutilise les tailles de dossiers déjà mesurées (fichier IF_<cas>.info) :
        # on ne re-scannera que les éventuels NOUVEAUX dossiers à 0.
        cached = self._apply_cached_folder_sizes(inventory)
        self._fill_tree()
        self._update_summary(inventory)
        # Retrait automatique des sources déjà indexées côté Import.
        if hasattr(self.app, "import_tab"):
            self.app.import_tab.apply_inventory()
        n = len(rows)
        unk = len(inventory["folder_unknown"])
        # Bouton de scan en vert s'il reste des dossiers à taille 0.
        self._set_scan_alert(bool(unk))
        msg = i18n.t("inventory.n_sources_read", "{n} source(s) lue(s) dans le cas.", n=n)
        if inventory.get("is_compound"):
            msg = self._compound_report(inventory, n)
        if cached:
            info_name = os.path.basename(
                case_info.info_path(self.app.case_meta["folder"], self.app.case_meta["name"]))
            msg += "\n" + i18n.t(
                "inventory.n_cached_folders",
                "{n} dossier(s) déjà mesuré(s) repris du fichier {f}.", n=cached, f=info_name)
        if unk:
            msg += "\n" + i18n.t(
                "inventory.n_unknown_folders",
                "{n} dossier(s) sans taille reportée — bouton « Scanner les dossiers à 0 » "
                "pour les mesurer.", n=unk)
        messagebox.showinfo(i18n.t("inventory.sources_title", "Inventaire des sources"), msg)
        # Consigne1 : cohérence taille du cas (case.xml) vs somme des sources.
        self._check_size_consistency()

    def _compound_report(self, inventory, n_sources) -> str:
        """Résumé « Lire les sources » d'un cas compound : une ligne par sous-cas.

        Les sous-cas en échec (dossier hors du poste, IntellaCmd en erreur) sont
        listés explicitement : l'inventaire est alors PARTIEL et il ne faut pas
        laisser croire qu'il est complet.
        """
        reports = inventory.get("subcase_reports", [])
        ok = [r for r in reports if r["ok"]]
        msg = i18n.t(
            "inventory.compound_read",
            "{n} source(s) lue(s) sur {k}/{t} sous-cas.",
            n=n_sources, k=len(ok), t=len(reports))
        for r in reports:
            if r["ok"]:
                msg += "\n  • " + i18n.t(
                    "inventory.compound_sub_ok", "{n} : {c} source(s)",
                    n=r["name"], c=r["source_count"])
            else:
                msg += "\n  ✕ " + i18n.t(
                    "inventory.compound_sub_ko", "{n} : non lu — {e}",
                    n=r["name"], e=r["error"])
        if len(ok) < len(reports):
            msg += "\n\n" + i18n.t(
                "inventory.compound_partial",
                "Inventaire PARTIEL : les sources des sous-cas non lus manquent.")
        return msg

    def _apply_cached_folder_sizes(self, inventory) -> int:
        """Applique les tailles de dossiers déjà mémorisées (IF_<cas>.info).

        Pour chaque dossier à 0 dont la taille est connue du cache : renseigne la
        ligne, l'intègre à ``known_bytes`` et le retire de ``folder_unknown``.
        Retourne le nombre de dossiers résolus par le cache.
        """
        meta = self.app.case_meta
        if not meta:
            return 0
        cache = case_info.get_folder_sizes(meta["folder"], meta["name"])
        if not cache:
            return 0
        applied, extra, still_unknown = 0, 0, []
        for f in inventory.get("folder_unknown", []):
            key = path_parser.normalize_path(f["path"]).lower()
            if key in cache:
                b = int(cache[key])
                for r in self.rows:
                    if r.get("Chemin") == f["path"]:
                        r["Taille"] = config.human_size(b) if b else "0"
                        r["Octets"] = str(b)
                extra += b
                applied += 1
            else:
                still_unknown.append(f)
        if applied:
            inventory["folder_unknown"] = still_unknown
            inventory["known_bytes"] = (inventory.get("known_bytes", 0) or 0) + extra
            info_name = os.path.basename(case_info.info_path(meta["folder"], meta["name"]))
            self.app.log.log(i18n.t(
                "inventory.cache_applied_log",
                "{n} dossier(s) à 0 repris du cache {f} (total {t}).",
                n=applied, f=info_name, t=config.human_size(extra)))
        return applied

    def _set_scan_alert(self, on: bool):
        if on:
            self.btn_scan.config(bg="#16a34a", fg="white",
                                 activebackground="#15803d", activeforeground="white")
        else:
            self.btn_scan.config(**self._scan_btn_default)

    def _inventory_total_bytes(self) -> int:
        """Somme des tailles connues des sources lues (images + fichiers + dossiers
        mesurés). Les dossiers à 0 non encore scannés ne sont pas comptés."""
        inv = self.app.inventory or {}
        return inv.get("known_bytes", 0) or 0

    def _check_size_consistency(self):
        """Consigne1 : si la taille occupée (case.xml) est inférieure de plus de
        SIZE_TOLERANCE à la somme des sources lues, avertir (sources non/partiellement
        indexées) ; le garde-fou de dépassement utilisera la plus grande des deux."""
        meta = self.app.case_meta
        inv = self.app.inventory
        if not meta or not inv:
            return
        case_size = meta.get("size", 0) or 0
        inv_total = self._inventory_total_bytes()
        if inv_total <= 0:
            return
        if case_size < inv_total * (1 - self.SIZE_TOLERANCE):
            pct = (inv_total - case_size) / inv_total * 100
            bigger = max(case_size, inv_total)
            self.app.log.log(i18n.t(
                "inventory.size_mismatch_log",
                "Cohérence tailles : case.xml {c} < somme sources {s} (écart {p:.1f}%). "
                "Garde-fou dépassement basé sur {b}.",
                c=config.human_size(case_size), s=config.human_size(inv_total),
                p=pct, b=config.human_size(bigger)), level="WARN")
            messagebox.showwarning(
                i18n.t("inventory.size_mismatch_title", "Cohérence des tailles"),
                i18n.t(
                    "inventory.size_mismatch_body",
                    "La taille occupée du cas (case.xml : {c}) est inférieure de {p:.1f}% à "
                    "la somme des sources lues ({s}).\n\nCertaines sources listées ne semblent "
                    "pas (entièrement) indexées dans le cas.\n\nLe calcul d'un éventuel "
                    "dépassement utilisera la valeur la plus grande ({b}).",
                    c=config.human_size(case_size), p=pct, s=config.human_size(inv_total),
                    b=config.human_size(bigger)))

    def _update_summary(self, inv):
        meta = self.app.case_meta
        size_txt = config.human_size(meta["size"]) if meta else "?"
        if inv.get("is_compound"):
            reports = inv.get("subcase_reports", [])
            ok = sum(1 for r in reports if r["ok"])
            self.lbl_summary.config(text=i18n.t(
                "inventory.compound_case_summary",
                "Cas COMPOUND « {n} » — {c} source(s) sur {k}/{t} sous-cas — total {s}",
                n=inv['case_name'], c=inv['source_count'], k=ok, t=len(reports), s=size_txt))
            return
        if inv["source_count"] == 0:
            self.lbl_summary.config(text=i18n.t(
                "inventory.case_empty", "Cas « {n} » — vide (aucune source indexée).",
                n=inv['case_name']))
            return
        txt = i18n.t("inventory.case_summary", "Cas « {n} » — {c} source(s) — taille du cas {s}",
                    n=inv['case_name'], c=inv['source_count'], s=size_txt)
        unk = len(inv["folder_unknown"])
        if unk:
            txt += "  •  " + i18n.t(
                "inventory.n_scannable_folders", "{n} dossier(s) à 0 (scannables)", n=unk)
        self.lbl_summary.config(text=txt)

    def _fill_tree(self):
        self.tree.delete(*self.tree.get_children())
        self.tree["columns"] = self.columns
        widths = {"Nom": 240, "Type": 110, "Fuseau": 70, "Taille": 90,
                  "Octets": 110, "Segments": 70, "Chemin": 360, "Tâches": 360,
                  "Sous-cas": 200}
        for c in self.columns:
            label = i18n.t(_COLUMN_LABEL_KEYS.get(c, ""), c) if c in _COLUMN_LABEL_KEYS else c
            self.tree.heading(c, text=label)
            self.tree.column(c, width=widths.get(c, 150), anchor="w", stretch=False)
        for r in self.rows:
            self.tree.insert("", "end", values=[r.get(c, "") for c in self.columns])

    # ------------------------------------------------------------------ #
    # Scan facultatif des dossiers à taille 0                            #
    # ------------------------------------------------------------------ #
    def _scan_zero(self):
        """Mesure les dossiers que l'export XML reporte à 0 (mesure INDICATIVE).

        Contrairement à l'onglet Import, ces sources sont **déjà indexées** :
        leur volume ne conditionne pas le garde-fou (``case.xml/size`` fait foi),
        il affine seulement l'affichage. D'où deux différences assumées :
        les résultats partiels sont **conservés et persistés immédiatement**
        (une source du cas ne bougera plus), et l'annulation est sans conséquence.
        """
        inv = self.app.inventory
        if not inv or not inv.get("folder_unknown"):
            messagebox.showinfo(
                i18n.t("inventory.zero_folders_title", "Dossiers à 0"),
                i18n.t("inventory.zero_folders_none",
                      "Aucun dossier sans taille à mesurer.\nLisez d'abord les sources du cas."))
            return
        if self._scan_running:
            return
        folders = list(inv["folder_unknown"])
        self._scan_running = True
        self._scan_cancel = False
        self.btn_scan.config(state="disabled")
        self.scan_bar.start(len(folders), on_cancel=self._cancel_scan,
                            cancel_text=i18n.t("common.cancel_btn", "✕ Annuler"))
        self.scan_bar.set_step(1, len(folders), i18n.t(
            "inventory.measuring_progress", "Mesure des dossiers… {i}/{n}", i=1, n=len(folders)))
        self.app.log.log(i18n.t(
            "inventory.scan_start_log", "Scan de {n} dossier(s) à taille 0…", n=len(folders)))
        # Moteur de mesure partagé avec l'onglet Import (cf. `sizing`) : le worker
        # ne touche aucun widget, `_poll_scan` draine la file côté UI.
        self._scan_queue = queue.Queue()
        items = [{"key": f["path"], "path": f["path"],
                  "label": f.get("name") or f["path"], "type": config.SOURCE_TYPE_FOLDER}
                 for f in folders]
        threading.Thread(
            target=sizing.measure_sources,
            args=(items, self._scan_queue, lambda: self._scan_cancel),
            daemon=True).start()
        self.after(100, self._poll_scan)

    def _cancel_scan(self):
        self._scan_cancel = True
        self.scan_bar.cancelling(i18n.t("common.cancelling", "Annulation en cours…"))
        self.app.log.log(i18n.t("inventory.scan_cancel_log", "Scan des dossiers : annulation demandée."))

    def _poll_scan(self):
        try:
            while True:
                msg = self._scan_queue.get_nowait()
                if msg[0] == "progress":
                    self._scan_zero_progress(*msg[1:])
                elif msg[0] == "row":
                    self.scan_bar.step_done()
                else:
                    self._scan_zero_done(msg[1], msg[3])
                    return
        except queue.Empty:
            pass
        self.after(100, self._poll_scan)

    def _scan_zero_progress(self, i, total, label, files, nbytes, elapsed):
        if self._scan_cancel:
            return
        text = i18n.t("inventory.measuring_progress_named", "Mesure des dossiers… {i}/{n} : {f}",
                      i=i, n=total, f=label)
        if files:
            text += "  —  " + i18n.t(
                "common.scan_stats", "{f} fichiers, {b}, {s}s ({r}/s)",
                f=files, b=config.human_size(nbytes), s=int(elapsed),
                r=config.human_size(int(nbytes / elapsed)) if elapsed >= 1 else "…")
        self.scan_bar.set_step(i, total, text)

    def _scan_zero_done(self, results_map, cancelled=False):
        self._scan_running = False
        self._scan_cancel = False
        self.btn_scan.config(state="normal")
        self.scan_bar.stop()
        results = list(results_map.items())
        by_path = dict(results)
        for r in self.rows:
            b = by_path.get(r.get("Chemin"))
            if b is not None:
                r["Taille"] = config.human_size(b) if b else "0"
                r["Octets"] = str(b)
        self._fill_tree()
        total = sum(b for _p, b in results)
        # Intègre les dossiers mesurés à la somme inventaire. Après une
        # interruption, les dossiers NON mesurés restent listés (l'alerte de scan
        # reste donc allumée) : on ne prétend pas connaître ce qu'on n'a pas vu.
        restants = []
        if self.app.inventory is not None:
            restants = [f for f in (self.app.inventory.get("folder_unknown") or [])
                        if f["path"] not in by_path]
            self.app.inventory["known_bytes"] = self._inventory_total_bytes() + total
            self.app.inventory["folder_unknown"] = restants
        self._set_scan_alert(bool(restants))
        # Persistance IMMÉDIATE (contrairement à l'onglet Import) : ces sources
        # sont déjà indexées dans le cas, leur contenu ne bougera plus — même les
        # mesures d'un scan interrompu sont bonnes à garder.
        meta = self.app.case_meta
        if meta and results:
            if case_info.update_folder_sizes(meta["folder"], meta["name"], dict(results)):
                info_name = os.path.basename(case_info.info_path(meta['folder'], meta['name']))
                self.app.log.log(i18n.t(
                    "inventory.sizes_saved_log", "Tailles mémorisées dans {f}.", f=info_name))
        self.app.log.log(i18n.t(
            "inventory.folders_measured_log", "Dossiers mesurés : {n} — total {t}.",
            n=len(results), t=config.human_size(total)))
        if cancelled:
            self.app.log.log(i18n.t(
                "inventory.scan_cancelled_log",
                "Scan interrompu : {n} dossier(s) mesuré(s), {m} restant(s) à 0.",
                n=len(results), m=len(restants)), level="WARN")
            self.lbl_summary.config(text=i18n.t(
                "inventory.scan_cancelled_summary",
                "Scan interrompu — {n} dossier(s) mesuré(s) (total {t}), {m} restant(s) à 0.",
                n=len(results), t=config.human_size(total), m=len(restants)))
        else:
            self.lbl_summary.config(text=i18n.t(
                "inventory.folders_measured_summary",
                "{n} dossier(s) mesuré(s) — total {t} (intégré à la somme inventaire).",
                n=len(results), t=config.human_size(total)))
        self._check_size_consistency()

    def _info_profile(self):
        """Réglages d'indexation de la source sélectionnée → onglet Profils."""
        inv = self.app.inventory
        details = (inv or {}).get("sources_detail")
        title = i18n.t("inventory.info_profile", "Info Profil →")
        if not details:
            messagebox.showinfo(
                title, i18n.t("inventory.info_profile_no_inventory",
                              "Lisez d'abord les sources du cas (« Lire les sources »)."))
            return
        sel = self.tree.selection()
        if not sel:
            messagebox.showinfo(
                title, i18n.t("inventory.info_profile_no_selection",
                             "Sélectionnez une source dans le tableau."))
            return
        idx = self.tree.index(sel[0])
        if idx >= len(details):
            messagebox.showerror(
                title, i18n.t("inventory.info_profile_not_found",
                              "Source introuvable (re-lisez les sources)."))
            return
        src = details[idx]
        values = profile_translate.from_xml_source(src)
        name = src.get("name") or i18n.t("inventory.default_profile_name", "profil")
        if not values:
            messagebox.showinfo(
                title, i18n.t(
                    "inventory.info_profile_empty",
                    "La source « {n} » n'expose aucun réglage exploitable "
                    "(indexOptions/domainBoundaries vides).", n=name))
            return
        self.app.open_profiles_with(values, name)
        self.app.log.log(i18n.t(
            "inventory.info_profile_log",
            "Info Profil : réglages de « {n} » transférés à l'onglet Profils ({c} option(s)).",
            n=name, c=len(values)))

    def _export_xml(self):
        """Enregistre une copie du XML produit par « Lire les sources »."""
        inv = self.app.inventory or {}
        xml_path = inv.get("xml_path")
        title = i18n.t("inventory.export_xml", "Exporter le XML…")
        # Cas compound : un XML par sous-cas lu → on exporte le lot dans un
        # dossier, sinon on n'en enregistrerait qu'un sur N sans le dire.
        if inv.get("is_compound") and len(inv.get("xml_paths") or []) > 1:
            self._export_xml_compound(inv, title)
            return
        if not xml_path or not os.path.isfile(xml_path):
            messagebox.showinfo(
                title, i18n.t("inventory.export_xml_none",
                              "Aucun XML disponible.\nLancez d'abord « Lire les sources »."))
            return
        meta = self.app.case_meta
        case_part = config.sanitize_filename(meta["name"]) + "_" if meta else ""
        default = f"sources_{case_part}{config.now_compact()}.xml"
        path = filedialog.asksaveasfilename(
            defaultextension=".xml", initialfile=default,
            filetypes=[("XML", "*.xml"), (i18n.t("common.filetype_all", "Tous"), "*.*")])
        if not path:
            return
        try:
            shutil.copyfile(xml_path, path)
            self.app.log.log(i18n.t("inventory.export_xml_log", "XML des sources exporté : {p}", p=path))
            messagebox.showinfo(title, i18n.t("common.exported_to", "Exporté :\n{p}", p=path))
        except OSError as exc:
            messagebox.showerror(title, i18n.t("common.export_failed", "Échec :\n{e}", e=exc))

    def _export_xml_compound(self, inv, title):
        """Copie les XML de tous les sous-cas lus dans un dossier choisi.

        Un fichier par sous-cas, nommé d'après lui : le lot reste exploitable
        source par source (« Info Profil » travaille, lui, sur l'inventaire en
        mémoire, pas sur ces copies).
        """
        paths = [p for p in inv.get("xml_paths", []) if os.path.isfile(p)]
        if not paths:
            messagebox.showinfo(
                title, i18n.t("inventory.export_xml_none",
                              "Aucun XML disponible.\nLancez d'abord « Lire les sources »."))
            return
        dest = filedialog.askdirectory(title=i18n.t(
            "inventory.export_xml_dir", "Dossier où déposer les XML des sous-cas"))
        if not dest:
            return
        # Les XML sont dans l'ordre des sous-cas LUS (les autres n'en ont pas).
        names = [r["name"] for r in inv.get("subcase_reports", []) if r["ok"]]
        stamp = config.now_compact()
        written, failed = [], []
        for i, src in enumerate(paths):
            label = config.sanitize_filename(names[i] if i < len(names) else f"souscas_{i + 1}")
            out = os.path.join(dest, f"sources_{label}_{stamp}.xml")
            try:
                shutil.copyfile(src, out)
                written.append(out)
            except OSError as exc:
                failed.append(f"{label} : {exc}")
        self.app.log.log(i18n.t(
            "inventory.export_xml_compound_log",
            "XML des sous-cas exportés : {n} fichier(s) dans {d}.", n=len(written), d=dest))
        msg = i18n.t("inventory.export_xml_compound_msg",
                     "{n} XML exporté(s) dans :\n{d}", n=len(written), d=dest)
        if failed:
            msg += "\n\n" + i18n.t("inventory.export_xml_compound_failed",
                                    "Échecs :\n{e}", e="\n".join(failed))
            messagebox.showwarning(title, msg)
        else:
            messagebox.showinfo(title, msg)

    def _export_case_tasks(self):
        """Exporte les tâches dédupliquées de l'inventaire du cas (JSON).

        Permet de vérifier la déduplication par signature : 1 objet par tâche
        logique (les UUID propres à chaque source sont fusionnés). Format
        ``tasks.json`` (réutilisable comme fichier de tâches)."""
        inv = self.app.inventory or {}
        objs = inv.get("case_tasks") or []
        title = i18n.t("inventory.export_tasks", "Exporter les tâches du cas…")
        if not objs:
            messagebox.showinfo(
                title, i18n.t("inventory.export_tasks_none",
                              "Aucune tâche sur les sources de ce cas.\n"
                              "Lisez d'abord les sources (« Lire les sources »)."))
            return
        meta = self.app.case_meta
        case_name = (meta["name"] if meta else "") or "Case"
        safe = config.sanitize_filename(case_name)
        default = f"taches_cas_{safe}_{config.now_compact()}.json"
        path = filedialog.asksaveasfilename(
            defaultextension=".json", initialfile=default,
            filetypes=[("JSON", "*.json"), (i18n.t("common.filetype_all", "Tous"), "*.*")])
        if not path:
            return
        try:
            with open(path, "w", encoding="utf-8") as f:
                json.dump(objs, f, ensure_ascii=False, indent=2)
            self.app.log.log(i18n.t(
                "inventory.export_tasks_log",
                "Tâches du cas exportées ({n} tâche(s) dédupliquée(s)) : {p}",
                n=len(objs), p=path))
            messagebox.showinfo(title, i18n.t(
                "inventory.export_tasks_msg",
                "{n} tâche(s) dédupliquée(s) exportée(s) :\n{p}\n\n"
                "1 objet = 1 tâche logique (UUID par source fusionnés par signature).",
                n=len(objs), p=path))
        except OSError as exc:
            messagebox.showerror(title, i18n.t("common.export_failed", "Échec :\n{e}", e=exc))

    def _export_csv(self):
        title = i18n.t("common.export_title", "Export")
        if not self.rows:
            messagebox.showinfo(title, i18n.t(
                "inventory.export_csv_none", "Lisez d'abord les sources d'un cas."))
            return
        meta = self.app.case_meta
        case_part = config.sanitize_filename(meta["name"]) + "_" if meta else ""
        default = f"inventaire_{case_part}{config.now_compact()}.csv"
        path = filedialog.asksaveasfilename(
            defaultextension=".csv", initialfile=default,
            filetypes=[("CSV", "*.csv"), (i18n.t("common.filetype_all", "Tous"), "*.*")],
        )
        if not path:
            return
        try:
            case_export.export_csv(self.rows, self.csv_columns, path)
            self.app.log.log(i18n.t("inventory.export_csv_log", "Inventaire exporté en CSV : {p}", p=path))
            messagebox.showinfo(title, i18n.t("common.exported_to", "Exporté :\n{p}", p=path))
        except OSError as exc:
            messagebox.showerror(title, i18n.t("common.export_failed", "Échec :\n{e}", e=exc))
