"""Onglet Import : collage des sources, récapitulatif (tailles + tâches), génération.

Le cas cible (emplacement + nom + utilisateur) est **verrouillé** : il provient de
l'étape « 1. Le cas » (lecture de ``case.xml``). La sortie est
automatique : ``Script\\Cas\\<nom>\\scripts`` (+ ``logs``). Le bouton « Valider les
opérations » recroise un re-scan du cas et l'analyse des logs d'import.
"""

import csv
import json
import os
import queue
import re
import subprocess
import threading
import time
import tkinter as tk
from tkinter import filedialog, messagebox, ttk

import case_export
import case_info
import config
import dnd_windows
import forensic_scan
import generator
import i18n
import json_builder
import models
import op_validation
import path_parser
import profiles
import sizing
import task_builder
import ui_theme
import validation
from ui_widgets import MeasureBar, Tooltip, make_button, make_dialog

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
        self._size_running = False  # calcul de taille en cours (anti double-clic)
        self._scan_running = False  # exploration d'un dossier d'images en cours
        self._scan_roots: list = []      # dossiers du dernier dépôt (relance récursive)
        self._scan_was_recursive = False
        self._scan_cancel = False   # annulation demandée (lue par le worker)
        self._size_cancel = False   # annulation demandée (lue par le worker)
        self._size_by_key = {}      # chemin -> Source (retour du moteur de mesure)
        # Mesures d'un calcul INTERROMPU, réutilisées à la relance (reprise) puis
        # oubliées dès qu'un calcul va au bout — sinon on ne pourrait plus
        # remesurer une source allégée entre-temps.
        self._resume_sizes = {}
        # Tailles mesurées cette session, EN ATTENTE d'écriture dans IF_<cas>.info :
        # persistées seulement pour les sources confirmées dans le cas par
        # « Valider les opérations » (une source pas encore importée peut être
        # allégée entre-temps → une taille mise en cache trop tôt serait fausse).
        self._pending_sizes = {}   # chemin (tel que saisi) -> octets
        self._import_proc = None   # Popen du .bat en cours (auto-validation à la fin)
        self._apres_mesure = None  # suite à exécuter à la fin d'une mesure
        self._auto_validate = True  # prérequis (exe + user) vérifiés au lancement
        # Alimente l'étape 3 du fil de navigation (cf. ui_nav) : tant qu'aucune
        # validation n'a confirmé les sources dans le cas, l'import n'est pas
        # « fait ».
        self._last_validation_ok = False

        self._build_params()
        self._build_panels()
        self._build_recap()
        self._build_actions()
        self._load_tasks(show_error=False)  # tâches par défaut au démarrage
        self.apply_case_meta()              # reflète un cas déjà détecté

    # ------------------------------------------------------------------ #
    def _build_params(self):
        """Paramètres du cas cible : **une ligne de rappel, un volet replié** (D3).

        Ces cinq lignes — cas, emplacement, limite, fuseau, fichier de tâches,
        arguments, intégrité — sont fixées pour toute une session de travail et
        occupaient ~148 px en permanence, soit un cinquième d'un écran de
        portable, au-dessus des deux zones où l'on travaille réellement. Elles
        restent toutes là, derrière « Modifier ▾ » ; ce qu'on lit en permanence
        est leur résumé.
        """
        s = self.app.settings
        theme = self.app.theme

        bandeau = ttk.Frame(self, style="Surface.TFrame")
        bandeau.pack(fill="x", padx=0, pady=(0, theme.gap))
        self.params_line = ttk.Frame(bandeau, style="Surface.TFrame")
        self.params_line.pack(fill="x", padx=theme.pad, pady=4)

        # Verrouillés : renseignés depuis case.xml via apply_case_meta().
        self.var_case = tk.StringVar(value=s.get("last_case"))
        self.var_casename = tk.StringVar(value=s.get("casename"))
        # Modifiables :
        self.var_tasks = tk.StringVar(value=s.get("tasks_path") or config.default_tasks_path())
        self.var_tz = tk.StringVar(value=s.get("timezone") or config.DEFAULT_TIMEZONE)
        self.var_limit = tk.StringVar(value=s.get("limit_gb") or str(config.DEFAULT_SIZE_LIMIT_GB))
        self.var_extra = tk.StringVar(value=s.get("extra"))

        # « Modifier » colle au résumé plutôt que de fuir à droite de l'écran :
        # posé au bout d'une ligne de 1 500 px, il était introuvable (11/09/2026).
        self.lbl_params = ttk.Label(self.params_line, text="", style="HintSurface.TLabel")
        self.lbl_params.pack(side="left")
        self.btn_params = make_button(
            self.params_line, i18n.t("import.params_edit", "Modifier ▾"),
            self._toggle_params)
        self.btn_params.pack(side="left", padx=(12, 0))

        self.params_detail = ttk.Frame(bandeau, style="Soft.TFrame")
        self._params_open = False

        frame = ttk.Frame(self.params_detail, style="Soft.TFrame")
        frame.pack(fill="x", padx=theme.pad, pady=theme.gap)
        frame.columnconfigure(1, weight=1)
        frame.columnconfigure(3, weight=2)

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
        self.var_skip_integrity = tk.BooleanVar(value=True)
        chk = ttk.Checkbutton(
            frame, variable=self.var_skip_integrity,
            text=i18n.t("import.skip_integrity",
                       "Ne pas vérifier l'intégrité des sources "
                       "(images multi-tronçons — contourne le bug Vound)"),
            command=self._on_skip_integrity_toggle)
        chk.grid(row=4, column=0, columnspan=4, sticky="w", padx=6, pady=(0, 4))

        # Le résumé doit suivre ce qu'on modifie dans le volet, sinon il ment
        # dès la première correction (constat de la relecture : un rappel faux
        # est pire qu'un rappel absent).
        for var in (self.var_casename, self.var_case, self.var_limit, self.var_tz,
                    self.var_tasks, self.var_skip_integrity):
            var.trace_add("write", lambda *_: self._refresh_params_summary())
        self._refresh_params_summary()

    def _toggle_params(self):
        self._params_open = not self._params_open
        if self._params_open:
            self.params_detail.pack(fill="x", before=None)
            self.btn_params.configure(text=i18n.t("import.params_close", "Replier ▴"))
        else:
            self.params_detail.pack_forget()
            self.btn_params.configure(text=i18n.t("import.params_edit", "Modifier ▾"))

    def _refresh_params_summary(self):
        """Une ligne qui dit tout ce que le volet replié contient."""
        if not hasattr(self, "lbl_params"):
            return
        nom = self.var_casename.get().strip()
        integrite = (i18n.t("import.integrity_off", "intégrité des sources non vérifiée")
                     if self.var_skip_integrity.get()
                     else i18n.t("import.integrity_on", "intégrité des sources vérifiée"))
        taches = os.path.basename(self.var_tasks.get().strip()) or "—"
        morceaux = [
            i18n.t("import.summary_case", "Cas cible : {n}",
                   n=nom or i18n.t("import.summary_nocase", "aucun")),
            i18n.t("import.summary_limit", "limite {g} Go", g=self.var_limit.get().strip()),
            i18n.t("import.summary_tz", "fuseau {t}", t=self.var_tz.get().strip()),
            i18n.t("import.summary_tasks", "tâches {f}", f=taches),
            integrite,
        ]
        self.lbl_params.configure(text="  ·  ".join(morceaux))

    def _build_panels(self):
        # PanedWindow : la poignée entre les panneaux de collage et « Sources à
        # importer » se tire à la souris (demande du 08/09/2026) — selon le
        # moment on veut voir les chemins collés ou le tableau, pas les deux.
        self.split = ttk.PanedWindow(self, orient="vertical")
        self.split.pack(fill="both", expand=True, padx=0, pady=0)
        haut = ttk.Frame(self.split)
        self.split.add(haut, weight=1)
        frame = ttk.Frame(haut)
        frame.pack(fill="both", expand=True, padx=8, pady=4)
        frame.columnconfigure(0, weight=1)
        frame.columnconfigure(1, weight=1)
        # 🐞 Sans poids sur la LIGNE, réduire « Sources à importer » ne rendait
        # rien aux deux zones de collage : la grille gardait leur hauteur de
        # départ et la place gagnée restait vide (rapporté le 09/09/2026).
        frame.rowconfigure(0, weight=1)

        left = ttk.LabelFrame(frame, text=i18n.t(
            "import.images_panel", "Images forensiques (DISK_IMAGE) — 1 chemin/ligne"))
        left.grid(row=0, column=0, sticky="nsew", padx=(0, 5))
        self.txt_images = self._build_paste_text(left)

        right = ttk.LabelFrame(frame, text=i18n.t(
            "import.folders_panel", "Dossiers standard (FOLDER_OR_FILE) — 1 chemin/ligne"))
        right.grid(row=0, column=1, sticky="nsew", padx=(5, 0))
        self.txt_folders = self._build_paste_text(right)

        # Les deux panneaux ne traitent PAS un dossier de la même façon : à
        # gauche il est exploré, à droite il devient la source. C'est écrit sous
        # chaque zone, sinon le même geste donne deux résultats sans prévenir.
        # Descente dans les sous-dossiers : décochée **à l'installation**, et
        # depuis la v2.9 le défaut se règle (Maintenance → Options, mémorisé au
        # .ini). Un dossier de scellés voisine souvent avec d'autres cas ou des
        # copies de travail ; y descendre d'office ramènerait des images
        # étrangères — mais un utilisateur qui range toujours ses images d'un
        # cran plus bas ne doit pas recocher la case à chaque dépôt.
        self.var_recursive = tk.BooleanVar(
            value=self.app.settings.get("recursive_default", "0").strip()
            in ("1", "true", "oui", "vrai"))
        bar_images = self._panel_footer(left, i18n.t(
            "import.drop_images_hint",
            "Glissez ici des images ou des DOSSIERS : seules les images "
            "forensiques (1er tronçon) sont ajoutées."),
            self._pick_folder_for_images, self._pick_files_for_images)
        ttk.Checkbutton(
            bar_images, variable=self.var_recursive,
            text=i18n.t("import.recursive_chk", "Explorer les sous-dossiers"),
        ).pack(side="left", padx=(8, 0))
        self._panel_footer(right, i18n.t(
            "import.drop_folders_hint",
            "Glissez ici des dossiers ou des fichiers : ils sont ajoutés tels quels."),
            self._pick_folder_for_folders, self._pick_files_for_folders)

        # Bandeau d'exploration (masqué au repos) : un dossier de scellés sur
        # partage réseau se parcourt en minutes et doit rester interruptible.
        self.scan_bar = MeasureBar(haut, pack_opts={"anchor": "w", "fill": "x",
                                                    "padx": 12, "pady": (0, 4)})

        # Interrupteur de secours : `enable_dnd = 0` dans intellafeeder.ini coupe
        # le glisser-déposer sans recompiler. Il sous-classe la fenêtre du
        # widget — si un poste s'en accommode mal, il faut pouvoir travailler
        # quand même (collage et bouton « Ajouter un dossier… » suffisent).
        if self.app.settings.get("enable_dnd", "1").strip() in ("0", "false", "non"):
            self.app.log.log(i18n.t(
                "import.dnd_disabled",
                "Glisser-déposer désactivé par le fichier .ini (enable_dnd = 0)."))
            return
        for widget, handler in ((self.txt_images, self._drop_on_images),
                                (self.txt_folders, self._drop_on_folders)):
            if not dnd_windows.accept_files(widget, handler):
                self.app.log.log(i18n.t(
                    "import.dnd_unavailable",
                    "Glisser-déposer indisponible sur ce poste : utilisez le bouton "
                    "« Ajouter un dossier… » ou le collage."), level="WARN")
                break

    def _panel_footer(self, parent, hint: str, on_add_folder, on_add_files):
        """Ligne sous une zone de collage : ajouts + rappel du comportement.

        « Ajouter : Dossiers… Fichiers… » plutôt que deux boutons à libellé
        long — la place sous les panneaux est comptée (08/09/2026).
        """
        bar = ttk.Frame(parent)
        bar.pack(fill="x", padx=4, pady=(0, 4))
        ttk.Label(bar, text=i18n.t("import.add_label", "Ajouter :")).pack(side="left")
        make_button(bar, i18n.t("import.add_folders_btn", "Dossiers…"),
                    on_add_folder).pack(side="left", padx=(4, 2))
        make_button(bar, i18n.t("import.add_files_btn", "Fichiers…"),
                    on_add_files).pack(side="left", padx=2)
        ttk.Label(bar, text=hint, foreground="#64748b",
                  wraplength=380, justify="left").pack(side="left", padx=8)
        return bar

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

    # ------------------------------------------------------------------ #
    # Alimentation des panneaux (glisser-déposer et bouton d'ajout)        #
    # ------------------------------------------------------------------ #
    def _append_paths(self, txt, paths) -> int:
        """Ajoute des chemins à une zone de collage, sans doublon apparent.

        `path_parser.parse_lines` dédoublonne déjà à l'analyse ; ce filtre-ci
        évite seulement d'afficher deux fois la même ligne après deux dépôts.
        """
        existant = {path_parser.normalize_path(l).lower()
                    for l in txt.get("1.0", "end").splitlines() if l.strip()}
        nouveaux = []
        for p in paths:
            cle = path_parser.normalize_path(p).lower()
            if cle and cle not in existant:
                existant.add(cle)
                nouveaux.append(p)
        if not nouveaux:
            return 0
        courant = txt.get("1.0", "end").rstrip("\n")
        prefixe = (courant + "\n") if courant.strip() else ""
        txt.delete("1.0", "end")
        txt.insert("1.0", prefixe + "\n".join(nouveaux) + "\n")
        txt.see("end")
        return len(nouveaux)

    def _drop_on_folders(self, paths):
        """Panneau « Dossiers standard » : ce qu'on lâche devient une source.

        Aucune inspection, c'est le contrat : un dossier de travail hétérogène
        s'indexe tel quel, et c'est à l'utilisateur de savoir ce qu'il y met.
        """
        if self._compound_blocked() or self._busy_measuring():
            return
        n = self._append_paths(self.txt_folders, paths)
        self.app.log.log(i18n.t("import.dropped_folders_log",
                                "{n} chemin(s) ajouté(s) au panneau « Dossiers standard ».", n=n))

    def _drop_on_images(self, paths):
        """Panneau « Images forensiques » : un dossier veut dire « explore-le ».

        C'est ce panneau qui remplace l'outil externe de constitution des listes
        (demande du 07/09/2026) : on y lâche l'arborescence d'un scellé et il en
        sort une ligne par image, premier tronçon seulement.
        """
        if self._compound_blocked() or self._busy_measuring():
            return
        dossiers, images, refuses = forensic_scan.classify_paths(paths)
        if images:
            n = self._append_paths(self.txt_images, images)
            self.app.log.log(i18n.t("import.dropped_images_log",
                                    "{n} image(s) ajoutée(s) au panneau « Images forensiques ».", n=n))
        if refuses:
            self._report_rejected(refuses)
        if dossiers:
            self._scan_folders(dossiers)

    @staticmethod
    def _reason_label(raison: str) -> str:
        """Traduit un motif de refus de `forensic_scan` (identifiants stables).

        Le module de scan reste sans i18n — il est testé unitairement et ses
        constantes servent de clés ; seule leur présentation est traduite ici.
        """
        return {
            forensic_scan.REASON_UNKNOWN: i18n.t(
                "import.reason_unknown", "extension non reconnue comme image forensique"),
            forensic_scan.REASON_SEGMENT: i18n.t(
                "import.reason_segment", "segment non initial — indiquez seulement le 1er"),
            forensic_scan.REASON_VMDK_PART: i18n.t(
                "import.reason_vmdk", "fichier annexe VMDK (pas un disque à ouvrir seul)"),
        }.get(raison, raison)

    def _report_rejected(self, refuses):
        """Dit ce qui a été écarté et POURQUOI (jamais en silence)."""
        refuses = [(c, self._reason_label(r)) for c, r in refuses]
        for chemin, raison in refuses:
            self.app.log.log(i18n.t("import.rejected_log", "Écarté — {r} : {p}",
                                    r=raison, p=chemin), level="WARN")
        apercu = "\n".join(f"• {os.path.basename(c)} — {r}" for c, r in refuses[:8])
        if len(refuses) > 8:
            apercu += "\n…"
        messagebox.showinfo(
            i18n.t("import.rejected_title", "Éléments écartés"),
            i18n.t("import.rejected_body",
                   "{n} élément(s) n'ont pas été ajoutés :\n\n{d}\n\n"
                   "Le panneau « Images forensiques » n'accepte que les images "
                   "connues, et seulement leur premier tronçon.",
                   n=len(refuses), d=apercu))

    def _pick_folder_for_images(self):
        """Même traitement que le glisser-déposer, au clavier ou sans souris."""
        if self._compound_blocked() or self._busy_measuring():
            return
        chemin = filedialog.askdirectory(
            title=i18n.t("import.pick_scan_title", "Dossier à explorer (images forensiques)"),
            mustexist=True)
        if chemin:
            self._scan_folders([os.path.normpath(chemin)])

    def _pick_files_for_images(self):
        """Sélection de FICHIERS images (filtre sur les extensions connues).

        Le dialogue propose les formats reconnus, mais le tri final reste celui
        de `forensic_scan` : un `.ad2` choisi à la main est refusé comme il le
        serait au dépôt.
        """
        if self._compound_blocked() or self._busy_measuring():
            return
        motifs = "*.E01 *.Ex01 *.L01 *.Lx01 *.s01 *.ad1 *.dd *.001 *.vmdk *.vhd *.vhdx"
        chemins = filedialog.askopenfilenames(
            title=i18n.t("import.pick_images_title", "Fichiers image forensique"),
            filetypes=[(i18n.t("import.image_filetypes", "Images forensiques"), motifs),
                       (i18n.t("common.filetype_all", "Tous"), "*.*")])
        if chemins:
            self._drop_on_images([os.path.normpath(p) for p in chemins])

    def _pick_files_for_folders(self):
        """Sélection de FICHIERS pour le panneau « Dossiers standard » (tels quels)."""
        if self._compound_blocked() or self._busy_measuring():
            return
        chemins = filedialog.askopenfilenames(
            title=i18n.t("import.pick_files_title", "Fichiers à ajouter comme sources"),
            filetypes=[(i18n.t("common.filetype_all", "Tous"), "*.*")])
        if chemins:
            self._drop_on_folders([os.path.normpath(p) for p in chemins])

    def _pick_folder_for_folders(self):
        if self._compound_blocked() or self._busy_measuring():
            return
        chemin = filedialog.askdirectory(
            title=i18n.t("import.pick_folder_title", "Dossier à ajouter comme source"),
            mustexist=True)
        if chemin:
            self._drop_on_folders([os.path.normpath(chemin)])

    # -- exploration récursive (worker + file, comme la mesure de tailles) -- #
    def _scan_folders(self, dossiers, recursive=None):
        """``recursive=None`` : on suit la case à cocher. Forcé à True quand
        l'utilisateur accepte de descendre après un premier passage à vide."""
        if self._scan_running:
            return
        if recursive is None:
            recursive = bool(self.var_recursive.get())
        self._scan_roots = list(dossiers)     # pour reproposer en récursif
        self._scan_was_recursive = recursive
        self._scan_running = True
        self._scan_cancel = False
        self._scan_queue = queue.Queue()
        self.scan_bar.start_busy(
            i18n.t("import.scan_start", "Exploration de {d}…", d=dossiers[0]),
            on_cancel=self._cancel_scan,
            cancel_text=i18n.t("common.cancel_btn", "✕ Interrompre le scan"))
        self.app.log.log(i18n.t("import.scan_start_log",
                                "Exploration de {n} dossier(s) à la recherche d'images…",
                                n=len(dossiers)))
        threading.Thread(target=self._scan_worker,
                         args=(list(dossiers), recursive),
                         daemon=True).start()
        self.after(150, self._poll_scan)

    def _cancel_scan(self):
        self._scan_cancel = True
        self.scan_bar.cancelling(i18n.t("common.cancelling", "Interruption en cours…"))

    def _scan_worker(self, dossiers, recursive):
        """Thread : ne touche AUCUN widget, poste dans `_scan_queue` (cf. sizing)."""
        trouves, counts = [], {}
        dernier = [0.0]

        def progress(vus, images, courant):
            # Cadencé : un dossier de scellés a des milliers de sous-dossiers,
            # une notification par dossier saturerait la file.
            maintenant = time.monotonic()
            if maintenant - dernier[0] >= sizing.PROGRESS_INTERVAL:
                dernier[0] = maintenant
                self._scan_queue.put(("progress", vus, len(trouves) + images, courant))

        for dossier in dossiers:
            if self._scan_cancel:
                break
            found, c = forensic_scan.scan_folder(
                dossier, on_progress=progress, should_stop=lambda: self._scan_cancel,
                recursive=recursive)
            trouves += found
            for ext, n in c.items():
                counts[ext] = counts.get(ext, 0) + n
        self._scan_queue.put(("done", trouves, counts, self._scan_cancel))

    def _poll_scan(self):
        try:
            while True:
                msg = self._scan_queue.get_nowait()
                if msg[0] == "progress":
                    _kind, vus, images, courant = msg
                    self.scan_bar.set_text(i18n.t(
                        "import.scan_progress",
                        "Exploration… {d} dossier(s), {i} image(s) — {c}",
                        d=vus, i=images, c=os.path.basename(courant) or courant))
                else:
                    self._scan_done(msg[1], msg[2], msg[3])
                    return
        except queue.Empty:
            pass
        self.after(150, self._poll_scan)

    def _scan_done(self, trouves, counts, cancelled):
        self._scan_running = False
        self._scan_cancel = False
        self.scan_bar.stop()
        # Une exploration interrompue rend ce qu'elle a trouvé : le contraire
        # obligerait à tout refaire pour une liste qu'on avait déjà.
        n = self._append_paths(self.txt_images, trouves) if trouves else 0
        resume = forensic_scan.summarize_counts(counts)
        self.app.log.log(i18n.t("import.scan_done_log",
                                "Exploration terminée : {n} image(s) ajoutée(s){s}.",
                                n=n, s=(" — " + resume) if resume else ""))
        titre = i18n.t("import.scan_title", "Images forensiques")
        if not trouves:
            # Sans cette proposition, une exploration non récursive qui ne
            # ramène rien passe pour une panne du glisser-déposer — c'est ce qui
            # est arrivé le 08/09/2026, les images étant un cran plus bas.
            sous = (0 if self._scan_was_recursive
                    else sum(forensic_scan.count_subdirs(d) for d in self._scan_roots))
            if sous and messagebox.askyesno(titre, i18n.t(
                    "import.scan_none_subdirs",
                    "Aucune image forensique directement dans ce dossier.\n\n"
                    "Il contient {n} sous-dossier(s). Les explorer aussi ?",
                    n=sous)):
                self._scan_folders(self._scan_roots, recursive=True)
                return
            messagebox.showinfo(titre, i18n.t(
                "import.scan_none", "Aucune image forensique trouvée."))
        elif cancelled:
            messagebox.showinfo(titre, i18n.t(
                "import.scan_cancelled",
                "Exploration interrompue : {n} image(s) ajoutée(s) ({s}).\n\n"
                "Relancez l'exploration pour parcourir le reste.", n=n, s=resume))
        else:
            messagebox.showinfo(titre, i18n.t(
                "import.scan_added", "{n} image(s) ajoutée(s) : {s}.", n=n, s=resume))

    def _build_recap(self):
        bas = ttk.Frame(self.split)
        self.split.add(bas, weight=3)
        frame = ttk.LabelFrame(bas, text=i18n.t("import.recap_frame", "Sources à importer"))
        frame.pack(fill="both", expand=True, padx=8, pady=4)

        # UNE barre d'outils, et non plus deux (décision D4, 11/09/2026). Les
        # dix boutons sur deux rangées se valaient tous visuellement ; les cinq
        # qui ne servent qu'occasionnellement sont passés sous « ⋯ ». La barre
        # ne grandit plus non plus de deux boutons par tâche chargée : cocher
        # une colonne entière se fait maintenant par son en-tête (D5).
        toolbar = ttk.Frame(frame)
        toolbar.pack(fill="x", padx=4, pady=(4, 2))
        # Vert = l'action du panneau : c'est elle qui remplit le tableau.
        self.btn_analyze = make_button(toolbar, i18n.t("import.summarize", "▼ Analyser les chemins"),
                                       self.recapituler, color=config.ACTION_COLOR)
        self.btn_analyze.pack(side="left")
        # Neutre depuis le 10/09/2026 : « Analyser les chemins » mesure desormais
        # les lignes qui n'ont pas de taille, donc ce bouton n'est plus une etape
        # du parcours mais un rattrapage (remesurer une source allegee).
        self.btn_size = make_button(toolbar, i18n.t("import.compute_size", "Remesurer"),
                                    self.calculer_taille)
        self.btn_size.pack(side="left", padx=6)
        ttk.Separator(toolbar, orient="vertical").pack(side="left", fill="y", padx=6)
        self.btn_check_all = make_button(toolbar, i18n.t("import.check_all", "Tout cocher"),
                                         lambda: self._set_all_import(True))
        self.btn_check_all.pack(side="left")
        self.btn_uncheck_all = make_button(toolbar, i18n.t("import.uncheck_all", "Tout décocher"),
                                           lambda: self._set_all_import(False))
        self.btn_uncheck_all.pack(side="left", padx=4)
        ttk.Separator(toolbar, orient="vertical").pack(side="left", fill="y", padx=6)
        # Purge complète : rouge en contour, visible — enterrée sous « ⋯ », elle
        # était introuvable au moment où l'on en a le plus besoin, entre deux lots.
        self.btn_clear_all = make_button(
            toolbar, i18n.t("import.clear_all", "Tout vider"),
            lambda: self.vider_liste(tout=True), outline=config.DANGER_COLOR)
        self.btn_clear_all.pack(side="left")
        self._bind_tip(self.btn_clear_all, i18n.t(
            "import.clear_all_tip",
            "Efface le tableau ET les chemins collés au-dessus : on repart de zéro."))
        ttk.Separator(toolbar, orient="vertical").pack(side="left", fill="y", padx=6)
        # Profil par défaut : appliqué aux NOUVELLES sources et à toutes les
        # lignes quand on en change. Mémorisé au .ini — « Défaut Intella » n'est
        # plus imposé (07/09/2026), c'est l'utilisateur qui décide.
        ttk.Label(toolbar, text=i18n.t("import.default_profile_label", "Profil par défaut :")).pack(side="left")
        self.cb_default_profile = ttk.Combobox(toolbar, state="readonly", width=27,
                                               postcommand=self._refresh_default_profiles)
        memorise = self.app.settings.get("default_profile", profiles.DEFAULT_NAME)
        if not profiles.exists(memorise):
            memorise = profiles.DEFAULT_NAME     # profil supprimé depuis
        self.cb_default_profile.set(profiles.display_name(memorise))
        self.cb_default_profile.pack(side="left", padx=4)
        self.cb_default_profile.bind("<<ComboboxSelected>>", lambda _e: self._apply_profile_all())

        # « ⋯ » seul se lit « ·· » à l'écran, et rien ne dit que c'est un menu.
        # Rangé À LA SUITE des autres, et non collé au bord droit : aligné sur
        # la marge opposée, il paraissait appartenir à un autre panneau.
        ttk.Separator(toolbar, orient="vertical").pack(side="left", fill="y", padx=6)
        self.btn_more = make_button(toolbar, i18n.t("import.more", "Plus ▾"),
                                    self._show_more_menu)
        self.btn_more.pack(side="left")
        self._bind_tip(self.btn_more, i18n.t(
            "import.more_tip",
            "Exporter / importer une liste, recharger les tâches, "
            "reprendre les tâches du cas, vider la liste"))
        self._build_more_menu()

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
        # Déjà dans le cas : barrée et grisée (D7). Un fond rouge disait
        # « erreur » là où il n'y en a pas — c'est au contraire l'outil qui
        # fait son travail de dédoublonnage.
        self.tree.tag_configure("dup", foreground=config.UI_INK_3,
                                font=ui_theme.F_STRIKE)
        self.tree.tag_configure("odd", background=config.UI_ZEBRA)

        self.tooltip = Tooltip(self.tree)
        self.tree.bind("<Button-1>", self._on_click)
        self.tree.bind("<Double-1>", self._on_double_click)
        self.tree.bind("<Motion>", self._on_motion)
        self.tree.bind("<Leave>", lambda _e: self.tooltip.hide())

        # Bandeau de progression (masqué au repos) : scan long sur NAS → il faut
        # voir l'avancement et pouvoir interrompre. Sert aussi à la validation.
        self.size_bar = MeasureBar(frame)

    def _build_more_menu(self):
        """Actions occasionnelles (D4) : présentes, mais hors du chemin de l'œil."""
        m = tk.Menu(self, tearoff=0)
        m.add_command(label=i18n.t("import.export_list", "Exporter la liste…"),
                      command=self._export_recap)
        m.add_command(label=i18n.t("import.import_list", "Importer une liste…"),
                      command=self._import_recap)
        m.add_separator()
        m.add_command(label=i18n.t("import.reload_tasks", "Recharger les tâches"),
                      command=lambda: self._load_tasks(show_error=True))
        m.add_command(label=i18n.t("import.case_tasks", "Tâches du cas (inventaire)"),
                      command=self._use_case_tasks)
        m.add_command(label=i18n.t("import.tasks_check_all", "Tâches : tout cocher"),
                      command=lambda: self._set_all(True))
        m.add_command(label=i18n.t("import.tasks_uncheck_all", "Tâches : tout décocher"),
                      command=lambda: self._set_all(False))
        m.add_separator()
        # Geste destructeur : isolé en fin de menu, et il demande confirmation.
        m.add_command(label=i18n.t("import.clear_list", "Vider la liste"),
                      command=lambda: self.vider_liste(tout=False),
                      foreground=config.DANGER_COLOR)
        self.more_menu = m

    def _show_more_menu(self):
        b = self.btn_more
        try:
            self.more_menu.tk_popup(b.winfo_rootx(),
                                    b.winfo_rooty() + b.winfo_height())
        finally:
            self.more_menu.grab_release()

    def _compound_blocked(self) -> bool:
        """Vrai (+ message) si le cas sélectionné est un compound.

        Un compound ne fait que référencer des sous-cas : IntellaCmd refuse d'y
        ajouter une source. ``MainWindow`` grise déjà l'onglet ; cette garde
        protège la fonction elle-même (appels internes venus de l'Inventaire,
        évolution future de l'UI) — même logique de double garde que
        ``_busy_measuring``.
        """
        if not (self.app.case_meta or {}).get("is_compound"):
            return False
        messagebox.showwarning(
            i18n.t("import.compound_title", "Cas compound"),
            i18n.t("import.compound_body",
                   "« {n} » est un cas COMPOUND : il ne fait que référencer des "
                   "sous-cas et n'accepte aucune source.\n\nAjoutez les sources "
                   "dans l'un de ses sous-cas (sélectionnez-le comme cas dans "
                   "l'étape « 1. Le cas »).",
                   n=self.app.case_meta.get("name", "")))
        return True

    def _busy_measuring(self) -> bool:
        """Vrai (+ message) si une mesure est en cours : la liste ne doit pas bouger.

        Doublon volontaire du grisage de `_set_busy` : les boutons grisés
        protègent l'utilisateur, cette garde protège la fonction elle-même
        (raccourci clavier, appel interne, évolution future de l'UI).
        """
        if not self._size_running:
            return False
        messagebox.showinfo(
            i18n.t("import.size_title", "Taille"),
            i18n.t("import.busy_measuring",
                   "Calcul de taille en cours : la liste des sources ne peut pas être "
                   "modifiée. Attendez la fin de la mesure."))
        return True

    def _set_busy(self, busy: bool):
        """Verrouille les actions qui modifieraient la liste pendant une mesure.

        Le worker travaille sur un instantané de ``self.sources`` : si la liste
        est remplacée (« Analyser les chemins », « Importer une liste ») ou si des
        lignes disparaissent pendant le scan, les tailles mesurées atterrissent
        sur des objets devenus orphelins — sans erreur visible. On grise donc tout
        ce qui touche à la liste, plus les actions aval (Générer / Importer) qui
        n'ont pas de sens tant que les tailles ne sont pas connues.
        """
        state = "disabled" if busy else "normal"
        # « ⋯ » porte désormais Importer une liste et Vider la liste : le griser
        # protège la mesure aussi sûrement que de griser les anciens boutons.
        for w in (self.btn_analyze, self.btn_more, self.btn_check_all,
                  self.btn_uncheck_all, self.btn_clear_all, self.btn_generate,
                  self.btn_import, self.btn_run_all):
            w.config(state=state)
        self.cb_default_profile.config(state="disabled" if busy else "readonly")

    def _build_actions(self):
        """Une action principale, et les 3 étapes détaillées à la demande.

        Le parcours nominal enchaîne toujours Générer → Importer → Valider : en
        faire un seul bouton évite trois clics et deux confirmations (demande du
        08/09/2026). Les étapes restent accessibles — un .bat lancé hors
        application se valide encore à la main, et une génération seule sert à
        relire les fichiers avant de lancer.
        """
        bar = ttk.Frame(self, style="Surface.TFrame")
        bar.pack(fill="x", padx=0, pady=0)
        self.action_bar = bar

        # Le total quitte les deux lignes de texte gris sous le tableau : il se
        # lit maintenant **à gauche du bouton qu'il conditionne**, c'est-à-dire
        # là où l'œil se pose avant de cliquer.
        resume = ttk.Frame(bar, style="Surface.TFrame")
        resume.pack(side="left", padx=self.app.theme.pad, pady=5)
        self.lbl_total = ttk.Label(resume, text=i18n.t("import.zero_sources", "0 source"),
                                   style="Title.TLabel")
        self.lbl_total.pack(anchor="w")
        self.lbl_inventory = ttk.Label(resume, text="", style="HintSurface.TLabel")
        self.lbl_inventory.pack(anchor="w")

        self.btn_run_all = make_button(
            bar, i18n.t("import.run_all", "▶ Lancer l'import complet"),
            self.lancer_import_complet, color=config.ACTION_COLOR)
        self.btn_run_all.pack(side="right", padx=(4, self.app.theme.pad), pady=6)
        self.btn_steps = make_button(
            bar, i18n.t("import.steps_show", "Étapes ▾"), self._toggle_steps)
        self.btn_steps.pack(side="right", pady=6)

        # Étapes détaillées : masquées au repos, dépliées par « Étapes ▾ ».
        self.steps_bar = ttk.Frame(self)
        self._steps_visible = False
        self.btn_generate = make_button(
            self.steps_bar, i18n.t("import.generate", "Générer les fichiers d'import"),
            self.generer)
        self.btn_generate.pack(side="left")
        self.btn_import = make_button(
            self.steps_bar, i18n.t("import.run_import", "Importer (lancer le .bat)"),
            self.importer)
        self.btn_import.pack(side="left", padx=6)
        self.btn_validate = make_button(
            self.steps_bar, i18n.t("import.validate", "Valider les opérations"),
            self.valider_operations)
        self.btn_validate.pack(side="left", padx=6)

    def _toggle_steps(self):
        self._steps_visible = not self._steps_visible
        if self._steps_visible:
            self.steps_bar.pack(fill="x", padx=self.app.theme.pad, pady=(0, 6))
            self.btn_steps.config(text=i18n.t("import.steps_hide", "Étapes ▴"))
        else:
            self.steps_bar.pack_forget()
            self.btn_steps.config(text=i18n.t("import.steps_show", "Étapes ▾"))

    def lancer_import_complet(self):
        """Générer → Importer → Valider, sans confirmation intermédiaire.

        La validation est déclenchée par ``_poll_import`` dès que le .bat rend
        la main : l'enchaînement s'arrête de lui-même si la génération échoue
        (limite dépassée, tailles manquantes), avec son message habituel.
        """
        if self._compound_blocked() or self._busy_measuring():
            return
        # La génération EXIGE une taille par source cochée. Sans cette mesure
        # préalable, le bouton « tout faire » s'arrêtait net sur « Tailles non
        # calculées » — l'utilisateur devait aller cliquer « Calculer la taille »
        # puis revenir, ce qui vide le bouton de son sens (demande du
        # 10/09/2026). On mesure les manquantes, PUIS on enchaîne.
        manquantes = [s for s in self.sources
                      if s.import_selected and s.size_bytes is None]
        if manquantes:
            self.app.log.log(i18n.t(
                "import.autosize_log",
                "Import complet : mesure préalable de {n} source(s) sans taille.",
                n=len(manquantes)))
            self._apres_mesure = self._enchainer_import
            self.calculer_taille(only_missing=True, silencieux=True)
            return
        self._enchainer_import()

    def _enchainer_import(self):
        """Générer → Importer, une fois les tailles connues."""
        if self._compound_blocked() or self._busy_measuring():
            return
        if not self.generer(auto=True):
            return
        self.importer(auto=True)

    # ------------------------------------------------------------------ #
    # Cas cible (verrouillé, depuis l'inventaire / case.xml)             #
    # ------------------------------------------------------------------ #
    def apply_case_meta(self):
        """Renseigne le cas cible (verrouillé) depuis ``app.case_meta``."""
        meta = self.app.case_meta
        if meta and meta.get("is_compound"):
            # Compound : aucun cas cible exploitable (les sources vont dans les
            # sous-cas). On laisse les champs vides plutôt que d'afficher un cas
            # sur lequel « Générer » ne pourra jamais aboutir.
            self.var_case.set("")
            self.var_casename.set("")
            self.var_skip_integrity.set(True)
        elif meta:
            self.var_case.set(meta["folder"])
            self.var_casename.set(meta["name"])
            # Réglage d'intégrité mémorisé pour ce cas (IF_<cas>.info).
            self.var_skip_integrity.set(
                case_info.get_skip_integrity(meta["folder"], meta["name"]))
        else:
            self.var_case.set("")
            self.var_casename.set("")
            self.var_skip_integrity.set(True)
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
                      "Sélectionnez d'abord un cas (étape « 1. Le cas »)."))
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
        except Exception as exc:  # noqa: BLE001 — fichier de tâches écrit par
            # Intella ou par l'opérateur : JSON invalide, encodage, structure
            # inattendue, fichier disparu entre-temps. Aucun de ces cas ne doit
            # laisser l'onglet dans un état à moitié chargé.
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
                "Lancez « Lire les sources » dans l'étape « 1. Le cas »."))
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

        # D5 — l'en-tête d'une colonne COCHABLE bascule la colonne entière ;
        # les autres trient, comme avant. Cela retire de la barre d'outils les
        # deux boutons par tâche (« T1 ✓ », « T1 ✗ »), qui la faisaient déborder
        # dès qu'un fichier de tâches en comptait plus de trois.
        cochables = {"import"} | {self._task_colid(i) for i in range(len(self.tasks))}
        for c in cols:
            if c in cochables:
                self.tree.heading(c, text=self._heading_base[c],
                                  command=lambda col=c: self._toggle_column_by_heading(col))
            else:
                self.tree.heading(c, text=self._heading_base[c],
                                  command=lambda col=c: self._sort_by(col))
        self.tree.column("import", width=48, anchor="center", stretch=False)
        self.tree.column("name", width=320, anchor="w", stretch=True)
        self.tree.column("type", width=80, anchor="center", stretch=False)
        self.tree.column("size", width=90, anchor="e", stretch=False)
        self.tree.column("profile", width=120, anchor="w", stretch=False)
        for i in range(len(self.tasks)):
            self.tree.column(self._task_colid(i), width=64, anchor="center", stretch=False)
        self.tree.column("del", width=52, anchor="center", stretch=False)

        self._refresh_headings()
        self._refresh_tree()

    def _toggle_column_by_heading(self, colid: str):
        """Bascule toute une colonne cochable depuis son en-tête (D5).

        La bascule est **globale, pas alternée ligne à ligne** : s'il reste une
        case décochée on coche tout, sinon on décoche tout. C'est ce qu'on attend
        d'un « tout cocher », et cela reste prévisible sur une liste triée.
        """
        if self._busy_measuring():
            return
        if colid == "import":
            valeur = not all(s.import_selected for s in self.sources) if self.sources else True
            self._set_all_import(valeur)
            return
        for i in range(len(self.tasks)):
            if self._task_colid(i) == colid:
                tid = self.tasks[i]["id"]
                valeur = not all(tid in s.selected_task_ids for s in self.sources) \
                    if self.sources else True
                self._toggle_column(i, valeur)
                return

    def _refresh_headings(self):
        """Montre dans l'en-tête si la colonne est entièrement cochée (D5).

        Sans ce retour, rien ne distingue un en-tête cliquable d'un en-tête de
        tri, et on ne sait pas ce que le prochain clic va faire.
        """
        if not hasattr(self, "tree"):
            return
        def marque(tous):
            return config.CHECK if tous else config.UNCHECK
        src = self.sources
        try:
            tous = bool(src) and all(s.import_selected for s in src)
            self.tree.heading("import", text=f"{self._heading_base['import']} {marque(tous)}")
            for i, t in enumerate(self.tasks):
                tid = t["id"]
                tous = bool(src) and all(tid in s.selected_task_ids for s in src)
                colid = self._task_colid(i)
                self.tree.heading(colid, text=f"{self._heading_base[colid]} {marque(tous)}")
        except tk.TclError:
            pass

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
        if self._compound_blocked() or self._busy_measuring():
            return
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
            else:
                # Source neuve : elle prend le profil par défaut CHOISI (combo
                # mémorisé au .ini). Une source déjà listée garde le sien.
                s.profile = self.default_profile()
            merged.append(s)

        self.sources = merged
        self._sort_col = None
        removed = self._drop_indexed()  # retrait auto des déjà indexées
        self._refresh_tree()
        msg = i18n.t("import.summary_log", "Analyse : {n} source(s).", n=len(self.sources))
        if removed:
            msg += " " + i18n.t("import.summary_removed_log", "{n} déjà dans le cas : décochée(s) et barrée(s).", n=removed)
        self.app.log.log(msg)
        # La génération EXIGE une taille par source cochée : sans mesure, le
        # parcours s'arrête sur un refus. On enchaîne donc directement, mais
        # **uniquement sur les lignes non mesurées** — analyser deux fois de
        # suite ne doit pas relancer le scan de tout ce qui est déjà connu.
        self.calculer_taille(only_missing=True, silencieux=True)

    def _size_text(self, s):
        return config.human_size(s.size_bytes) if s.size_bytes is not None else "—"

    def _row_values(self, s):
        nom = s.name
        if self._is_indexed(s):
            nom += "  " + i18n.t("import.already_in_case", "— déjà dans le cas")
        values = [config.glyph(s.import_selected), nom,
                  config.type_label(s.source_type), self._size_text(s),
                  profiles.display_name(getattr(s, "profile", "défaut") or "défaut")]
        for t in self.tasks:
            values.append(config.glyph(t["id"] in s.selected_task_ids))
        values.append(_DEL_GLYPH)
        return values

    def _refresh_tree(self):
        self.tree.delete(*self.tree.get_children())
        for i, s in enumerate(self.sources):
            tags = ["dup"] if self._is_indexed(s) else []
            if i % 2:
                tags.append("odd")
            self.tree.insert("", "end", iid=str(i), values=self._row_values(s),
                             tags=tuple(tags))
        self._update_total()
        self._update_heading_arrows()
        self._refresh_headings()
        self._update_inventory_label()
        self.app.update_steps()

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
        """Vrai si l'inventaire (liste des sources) concerne le cas ciblé.

        La comparaison ignore le **nom d'hôte** d'un chemin UNC : le même cas
        s'ouvre indifféremment par nom NetBIOS ou par IP, et exiger la même
        écriture ferait passer l'inventaire pour étranger au cas — donc plus
        aucun retrait des sources déjà indexées.
        """
        inv = self.app.inventory
        if not inv:
            return False
        case = path_parser.normalize_path(self.var_case.get()).lower()
        if not case:
            return False
        if case == inv.get("case_path_key"):
            return True
        return path_parser.share_key(case) == path_parser.share_key(
            inv.get("case_path", "") or inv.get("case_path_key", ""))

    def _is_indexed(self, s) -> bool:
        r"""La source est-elle déjà dans le cas ? Chemin exact OU même partage.

        🐞 08/09/2026 : un cas réel mélange les écritures d'hôte (une source en
        ``\\IP\part\…``, les autres en ``\\NOM\part\…``). Comparer les chemins
        bruts laissait repartir à l'import une source déjà indexée. La
        correspondance « même partage, hôte différent » est journalisée pour
        rester vérifiable.
        """
        if not self._inventory_matches():
            return False
        inv = self.app.inventory
        if path_parser.normalize_path(s.path).lower() in inv["existing_paths"]:
            return True
        if path_parser.share_key(s.path) in (inv.get("existing_share_keys") or set()):
            self.app.log.log(i18n.t(
                "import.indexed_other_host",
                "Déjà dans le cas sous un autre nom de serveur : {p}", p=s.path))
            return True
        return False

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
        """Écarte de l'import les sources **déjà présentes dans le cas** (D7).

        Elles ne sont plus **retirées** de la liste mais **décochées et barrées**
        (décision du 11/09/2026). Retirer en silence une ligne que l'utilisateur
        venait de coller lui laissait croire à une perte : le journal seul en
        gardait trace, et il fallait le relire pour comprendre pourquoi 18 chemins
        collés donnaient 17 lignes. Retourne le nombre de lignes écartées.

        ⚠ Le dédoublonnage lui-même n'a pas changé : il compare toujours à hôte
        près (``path_parser.share_key``), un même cas mélangeant les écritures
        IP et nom NetBIOS d'un même partage.
        """
        if not self._inventory_matches():
            return 0
        n = 0
        for s in self.sources:
            if self._is_indexed(s) and s.import_selected:
                s.import_selected = False
                n += 1
        return n

    def apply_inventory(self):
        """Appelé quand l'inventaire (liste des sources) vient d'être lu.

        Retire automatiquement les sources déjà indexées du récapitulatif.
        Sans objet sur un cas compound (aucun import possible) : l'inventaire y
        décrit les sources des sous-cas, pas celles d'un cas cible.
        """
        if (self.app.case_meta or {}).get("is_compound"):
            return
        removed = self._drop_indexed()
        self._refresh_tree()
        if removed:
            self.app.log.log(i18n.t(
                "import.auto_removed_log", "{n} source(s) déjà indexée(s) décochée(s) automatiquement.",
                n=removed))

    def _update_inventory_label(self):
        if not hasattr(self, "lbl_inventory"):
            return
        meta = self.app.case_meta
        if not meta:
            self.lbl_inventory.config(
                foreground="#b45309",
                text=i18n.t("import.no_case_selected",
                           "ⓘ Aucun cas sélectionné — choisissez-le dans l'étape « 1. Le cas »."),
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
            messagebox.showinfo(title, i18n.t("import.recap_empty", "La liste des sources à importer est vide."))
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
                "import.recap_exported_log", "Liste exportée ({n} source(s)) : {p}",
                n=len(data), p=path))
            messagebox.showinfo(title, i18n.t(
                "import.recap_exported_msg", "{n} source(s) exportée(s) :\n{p}", n=len(data), p=path))
        except OSError as exc:
            messagebox.showerror(title, i18n.t("common.export_failed", "Échec :\n{e}", e=exc))

    def _import_recap(self):
        if self._busy_measuring():
            return
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
                "Remplacer la liste actuelle ({cur} source(s)) par {new} source(s) du fichier ?",
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
        msg = i18n.t("import.list_imported_log", "Liste importée : {n} source(s) depuis {p}",
                    n=len(self.sources), p=path)
        if removed:
            msg += " " + i18n.t("import.list_imported_removed", "({n} déjà dans le cas : décochée(s))." , n=removed)
        self.app.log.log(msg)
        info = i18n.t("import.n_sources_loaded", "{n} source(s) chargée(s).", n=len(self.sources))
        if removed:
            info += "\n" + i18n.t(
                "import.n_removed_auto", "{n} déjà indexée(s) dans le cas : décochée(s), elles restent visibles barrées.",
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
        if self._size_running:
            return          # mesure en cours : la liste ne doit pas bouger (✕, coches)
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
                "import.source_removed_log", "Source retirée de la liste : {n}", n=s.name))
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
        if self._size_running:
            return          # renommage interdit pendant la mesure (cf. _set_busy)
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
        cb = ttk.Combobox(self.tree, values=[profiles.display_name(n) for n in names],
                          state="readonly")
        current = getattr(s, "profile", profiles.DEFAULT_NAME) or profiles.DEFAULT_NAME
        if current not in names:
            current = profiles.DEFAULT_NAME
        cb.set(profiles.display_name(current))
        cb.place(x=x, y=y, width=max(w, 140), height=h)
        cb.focus_set()

        def commit(_=None):
            # Le combo montre un libellé, la source garde l'identifiant.
            val = profiles.internal_name(cb.get()) or profiles.DEFAULT_NAME
            s.profile = val
            self.tree.set(row, "profile", profiles.display_name(val))
            cb.destroy()

        cb.bind("<<ComboboxSelected>>", commit)
        cb.bind("<FocusOut>", lambda _e: cb.destroy())
        cb.bind("<Escape>", lambda _e: cb.destroy())

    def _refresh_default_profiles(self):
        """Alimente le combobox « Profil par défaut » avec les profils existants."""
        self.cb_default_profile["values"] = [profiles.display_name(n)
                                             for n in profiles.list_names()]

    def default_profile(self) -> str:
        """Identifiant du profil à donner aux NOUVELLES sources."""
        nom = profiles.internal_name(self.cb_default_profile.get())
        return nom if nom and profiles.exists(nom) else profiles.DEFAULT_NAME

    def _apply_profile_all(self):
        """Applique le profil choisi (combobox) à TOUTES les lignes du récap.

        Le choix est mémorisé : il vaut aussi pour les sources analysées plus
        tard, y compris au prochain démarrage.
        """
        prof = self.default_profile()
        self.app.settings.set("default_profile", prof)
        for s in self.sources:
            s.profile = prof
        self._refresh_tree()
        self.app.log.log(i18n.t(
            "import.profile_applied_all_log", "Profil « {p} » appliqué à toutes les sources ({n}).",
            p=profiles.display_name(prof), n=len(self.sources)))

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

    def vider_liste(self, tout: bool = True):
        """Repart de zéro : tableau **et** zones de chemins collés (11/09/2026).

        Jusque-là, « Vider la liste » ne touchait pas aux zones de collage, au
        motif qu'on repart souvent d'elles. À l'usage c'est l'inverse qui gêne :
        entre deux lots, on veut **purger l'écran d'un coup** et ne pas retrouver
        les chemins du lot précédent à la prochaine analyse. La confirmation dit
        exactement ce qui part.

        ``tout=False`` ne vide que le tableau (appelé par le menu « ⋯ »).
        """
        if self._compound_blocked() or self._busy_measuring():
            return
        titre = (i18n.t("import.clear_all", "Tout vider") if tout
                 else i18n.t("import.clear_list", "Vider la liste"))
        colles = sum(1 for zone in (self.txt_images, self.txt_folders)
                     for ligne in zone.get("1.0", "end").splitlines() if ligne.strip())
        if not self.sources and not (tout and colles):
            messagebox.showinfo(titre, i18n.t("import.clear_empty",
                                              "La liste est déjà vide."))
            return
        if tout:
            question = i18n.t(
                "import.clear_all_confirm",
                "Repartir de zéro ?\n\n{n} source(s) du tableau et {c} chemin(s) "
                "collé(s) seront effacés.", n=len(self.sources), c=colles)
        else:
            question = i18n.t(
                "import.clear_confirm",
                "Retirer les {n} source(s) de la liste ?\n\nLes chemins collés "
                "au-dessus sont conservés : « Analyser les chemins » les "
                "remettra.", n=len(self.sources))
        if not messagebox.askyesno(titre, question):
            return
        n = len(self.sources)
        self.sources = []
        self._pending_sizes = {}
        self._resume_sizes = {}
        self._sort_col = None
        if tout:
            for zone in (self.txt_images, self.txt_folders):
                zone.delete("1.0", "end")
        self._refresh_tree()
        self.app.log.log(
            i18n.t("import.clear_all_log",
                   "Onglet vidé : {n} source(s) et {c} chemin(s) collé(s).",
                   n=n, c=colles) if tout else
            i18n.t("import.clear_log",
                   "Liste des sources vidée ({n} retirée(s)).", n=n))

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
        if self._size_running:
            return          # réordonner pendant la mesure brouille les lignes
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
    def calculer_taille(self, only_missing: bool = False, silencieux: bool = False):
        """Mesure les sources cochées.

        ``only_missing`` : ne mesurer que celles qui n'ont **pas** de taille —
        c'est l'enchaînement automatique depuis « Analyser les chemins ».
        Remesurer tout à chaque analyse serait ruineux (un scellé réseau prend
        des dizaines de minutes) et effacerait le travail déjà fait.
        ``silencieux`` : pas de message quand il n'y a rien à mesurer, l'appel
        n'ayant pas été demandé explicitement par l'utilisateur.
        """
        if self._size_running:
            return                       # déjà en cours : le bouton est grisé, on ignore
        checked = [s for s in self.sources if s.import_selected]
        if only_missing:
            checked = [s for s in checked if s.size_bytes is None]
        if not checked:
            if silencieux:
                return
            messagebox.showinfo(
                i18n.t("import.size_title", "Taille"),
                i18n.t("import.no_checked",
                      "Aucune source cochée « Importer ».\nSeules les lignes cochées sont mesurées."))
            return
        self.app.log.log(i18n.t(
            "import.computing_size_log", "Calcul de la taille de {n} source(s) cochée(s)…", n=len(checked)))
        self._size_running = True
        self._size_cancel = False
        self._size_by_key = {s.path: s for s in checked}
        self.btn_size.config(state="disabled")
        self._set_busy(True)
        self.size_bar.start(len(checked), on_cancel=self._cancel_size,
                            cancel_text=i18n.t("common.cancel_btn", "✕ Interrompre le scan"))
        self.size_bar.set_step(1, len(checked), i18n.t(
            "import.size_progress", "Mesure {i}/{n} : {name}", i=1, n=len(checked), name="…"))
        # Les lignes en attente affichent « … » plutôt qu'une taille périmée.
        for s in checked:
            rid = self._row_id_of(s)
            if rid is not None:
                self.tree.set(rid, "size", "…")
        # Le worker ne touche PAS aux widgets : il poste ses avancées dans une
        # file, drainée par `_poll_size` sur le thread UI (tkinter n'est pas
        # thread-safe ; appeler `after` depuis le worker lève « main thread is
        # not in main loop » selon le moment).
        self._size_queue = queue.Queue()
        meta = self.app.case_meta
        cache = dict(case_info.get_folder_sizes(meta["folder"], meta["name"]) if meta else {})
        # Reprise après annulation : les sources déjà mesurées au tour précédent
        # ne sont pas rescannées. Vidé après un calcul mené à son terme, pour
        # qu'un nouveau clic remesure bien (source allégée entre-temps).
        cache.update({sizing.cache_key(k): v for k, v in self._resume_sizes.items()})
        items = [{"key": s.path, "path": s.path, "label": s.name, "type": s.source_type}
                 for s in checked]
        threading.Thread(
            target=sizing.measure_sources,
            args=(items, self._size_queue, lambda: self._size_cancel, cache),
            daemon=True).start()
        self.after(100, self._poll_size)

    def _cancel_size(self):
        """Demande l'arrêt : le worker s'arrête à la prochaine vérification."""
        self._size_cancel = True
        self.size_bar.cancelling(i18n.t("common.cancelling", "Interruption en cours…"))
        self.app.log.log(i18n.t("import.size_cancel_log", "Calcul des tailles : annulation demandée."))

    def _row_id_of(self, source):
        """Identifiant de ligne du Treeview pour ``source`` (index dans ``sources``)."""
        try:
            rid = str(self.sources.index(source))
        except ValueError:
            return None
        return rid if self.tree.exists(rid) else None

    def _poll_size(self):
        """Draine la file du moteur de mesure sur le thread UI (cf. `sizing`)."""
        try:
            while True:
                msg = self._size_queue.get_nowait()
                if msg[0] == "progress":
                    self._size_progress(*msg[1:])
                elif msg[0] == "row":
                    self._size_row_done(msg[1], msg[2])
                elif msg[0] == "done":
                    # Test explicite sur « done » (et non un `else` attrape-tout) :
                    # le message porte un 5ᵉ élément depuis le 18/09/2026, et un
                    # type inconnu ne doit pas passer pour une fin de mesure.
                    self._size_done(*msg[1:])
                    return
        except queue.Empty:
            pass
        self.after(100, self._poll_size)

    def _size_progress(self, i, total, label, files, nbytes, elapsed):
        if self._size_cancel:
            return                      # « Annulation en cours… » reste affiché
        text = i18n.t("import.size_progress", "Mesure {i}/{n} : {name}", i=i, n=total, name=label)
        if files:
            text += "  —  " + i18n.t(
                "common.scan_stats", "{f} fichiers, {b}, {s}s ({r}/s)",
                f=files, b=config.human_size(nbytes), s=int(elapsed),
                r=config.human_size(int(nbytes / elapsed)) if elapsed >= 1 else "…")
        self.size_bar.set_step(i, total, text)

    def _size_row_done(self, key, size_bytes):
        """Affiche la taille dès qu'une source est mesurée (retour au fil de l'eau)."""
        source = self._size_by_key.get(key)
        if source is not None:
            source.size_bytes = size_bytes
            rid = self._row_id_of(source)
            if rid is not None:
                self.tree.set(rid, "size", self._size_text(source))
        self.size_bar.step_done()

    def _size_done(self, results=None, cached_keys=None, cancelled=False, failed=None):
        # `failed` : sources dont la lecture a échoué (partage déconnecté,
        # dossier ou fichier illisible). Elles ne sont PAS mesurées — mieux vaut
        # une taille manquante, visible, qu'une taille fausse (cf. `sizing`).
        if failed:
            self.app.log.log(i18n.t(
                "common.measure_io_error",
                "Mesure incomplète pour {n} source(s) : lecture impossible "
                "(partage déconnecté ou fichier verrouillé). Elles restent à mesurer.",
                n=len(failed)))
        # try/finally : une erreur d'affichage ne doit jamais laisser l'UI grisée.
        try:
            self._size_finish(results or {}, cached_keys or set(), cancelled)
        finally:
            self._size_running = False
            self._size_cancel = False
            self.btn_size.config(state="normal")
            self.size_bar.stop()
            self._set_busy(False)
        # Suite éventuelle (« Lancer l'import complet » qui attendait les
        # tailles). Posée APRÈS le déverrouillage de l'UI, sinon la génération
        # partirait sur des boutons encore grisés. Abandonnée si l'utilisateur a
        # interrompu la mesure : il a dit non, on ne le contourne pas.
        suite, self._apres_mesure = getattr(self, "_apres_mesure", None), None
        if suite and not cancelled:
            self.after(50, suite)

    def _size_finish(self, results, cached_keys, cancelled=False):
        # Seules les sources mesurées ce tour-ci sont à persister : celles reprises
        # du cache y sont déjà.
        measured = {k: v for k, v in results.items() if k not in cached_keys}
        for i, s in enumerate(self.sources):
            if self.tree.exists(str(i)):
                self.tree.set(str(i), "size", self._size_text(s))
        self._update_total()
        total = sum((s.size_bytes or 0) for s in self.sources if s.import_selected)
        if cancelled:
            # Les sources non mesurées restent sans taille → « Générer » les
            # refusera tant qu'elles ne sont pas mesurées (contrat v2.5h).
            self._resume_sizes.update(results)
            manquantes = sum(1 for s in self.sources if s.import_selected and s.size_bytes is None)
            self.app.log.log(i18n.t(
                "import.size_cancelled_log",
                "Calcul interrompu : {n} source(s) mesurée(s), {m} restante(s) sans taille.",
                n=len(results), m=manquantes), level="WARN")
            messagebox.showinfo(
                i18n.t("import.size_title", "Taille"),
                i18n.t("import.size_cancelled_msg",
                       "Mesure interrompue.\n\n{n} source(s) mesurée(s), {m} sans taille.\n"
                       "Les sources sans taille bloqueront la génération : relancez "
                       "« Calculer la taille » pour les compléter (les mesures déjà "
                       "faites ne seront pas refaites).", n=len(results), m=manquantes))
        else:
            self._resume_sizes = {}     # calcul complet : plus rien à reprendre
            self.app.log.log(i18n.t(
                "import.size_done_log", "Calcul des tailles terminé. Total cochées : {t}.",
                t=config.human_size(total)))
        if cached_keys:
            self.app.log.log(i18n.t(
                "import.size_cache_reused_log",
                "{n} source(s) déjà mesurée(s) reprise(s) du cache (IF_<cas>.info).",
                n=len(cached_keys)))
        # Mesures NON persistées ici : une source pas encore importée peut être
        # allégée (suppression de sous-dossiers) avant l'import, auquel cas un
        # cache écrit trop tôt fige une taille périmée. Elles ne sont écrites dans
        # IF_<cas>.info qu'une fois la source confirmée dans le cas, par
        # « Valider les opérations » (cf. `_persist_measured_sizes`).
        if measured:
            self._pending_sizes.update(measured)
            self.app.log.log(i18n.t(
                "import.size_pending_log",
                "{n} taille(s) mesurée(s) — mémorisée(s) dans IF_<cas>.info seulement "
                "après « Valider les opérations ».", n=len(measured)))

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

    def generer(self, auto: bool = False) -> bool:
        """Écrit les fichiers d'import. Retourne True si la génération a eu lieu.

        ``auto`` : enchaînement automatique (bouton « Lancer l'import complet »),
        le compte rendu part au journal au lieu d'ouvrir une fenêtre.
        """
        if self._compound_blocked():
            return False
        params = self._params()
        if not self.app.case_meta:
            messagebox.showerror(
                i18n.t("common.case_required_title", "Cas requis"),
                i18n.t("import.select_case_target",
                      "Sélectionnez d'abord un cas dans l'étape « 1. Le cas »."))
            return False
        # Seules les lignes cochées « Importer » sont générées.
        selected = [s for s in self.sources if s.import_selected]
        if not selected:
            messagebox.showerror(
                i18n.t("import.empty_selection_title", "Sélection vide"),
                i18n.t("import.empty_selection_body",
                      "Cochez au moins une source dans la colonne « Imp. » (Importer)."))
            return False
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
            return False

        # Tailles obligatoires : le garde-fou de limite n'a aucun sens sans elles.
        # On ne les calcule plus en silence ici (scan long, UI figée, aucune
        # progression) : l'utilisateur passe par « Calculer la taille ».
        missing = [s for s in selected if s.size_bytes is None]
        if missing:
            messagebox.showerror(
                i18n.t("import.sizes_required_title", "Tailles non calculées"),
                i18n.t("import.sizes_required_body",
                       "{n} source(s) cochée(s) n'ont pas de taille :\n{list}\n\n"
                       "Cliquez sur « Calculer la taille » avant de générer "
                       "(sans les tailles, le contrôle de la limite du cas est impossible).",
                       n=len(missing), list=self._format_list([s.name for s in missing], 12)))
            return False

        limit_b = self._limit_gb() * config.GB

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
            return False

        if warnings and not messagebox.askyesno(
            i18n.t("import.warnings_title", "Avertissements"),
            self._format_list(warnings) + "\n\n" + i18n.t(
                "import.generate_anyway", "Générer malgré tout ?")
        ):
            return False

        try:
            report = generator.generate(selected, params, self.tasks, self.app.log.log)
        except ValueError as exc:
            # Dernier verrou de `json_builder._q` : un caractère impossible à citer
            # dans le .bat (guillemet, retour à la ligne). `validation.collect` le
            # dit normalement avant d'arriver ici — si on y arrive quand même,
            # c'est qu'il vient d'ailleurs (nom de source, arguments suppl.).
            messagebox.showerror(
                i18n.t("import.corrections_needed", "Corrections nécessaires"), str(exc))
            return False
        except OSError as exc:
            messagebox.showerror(i18n.t("import.write_title", "Écriture"),
                                 i18n.t("common.export_failed", "Échec :\n{e}", e=exc))
            return False

        self.app.save_settings()
        if auto:
            self.app.log.log(i18n.t(
                "import.generated_log", "Fichiers d'import générés dans {p}.",
                p=os.path.abspath(report["output"])))
        else:
            self._show_report(report, len(selected))
        return True

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

    def importer(self, auto: bool = False):
        """``auto`` : lancé par « Lancer l'import complet », sans confirmation.

        Les GARDES restent actives (cas compound, .bat absent, import déjà en
        cours) : seule la question « continuer ? » est sautée — c'est elle que
        l'enchaînement doit éviter, pas les contrôles.
        """
        if self._compound_blocked():
            return
        title = i18n.t("import.run_import", "Importer (lancer le .bat)")
        if not self.app.case_meta:
            messagebox.showinfo(title, i18n.t(
                "import.select_case_short", "Sélectionnez d'abord un cas (étape « 1. Le cas »)."))
            return
        bat = self._main_bat_path()
        if not bat:
            messagebox.showwarning(title, i18n.t(
                "import.no_bat_found",
                "Aucun fichier d'import trouvé pour ce cas.\n"
                "Cliquez d'abord sur « Générer les fichiers d'import »."))
            return
        if self._import_proc is not None and self._import_proc.poll() is None:
            messagebox.showinfo(title, i18n.t(
                "import.already_running", "Un import est déjà en cours (fenêtre de console ouverte)."))
            return
        # Prérequis de la validation automatique vérifiés AVANT de lancer le .bat :
        # sinon l'utilisateur reçoit une erreur juste après un import réussi.
        exe = path_parser.clean_field(self.app.var_exe.get())
        user = self.app.var_user.get().strip()
        self._auto_validate = bool(exe and user)
        if not self._auto_validate and not messagebox.askyesno(
            title, i18n.t(
                "import.autovalidate_unavailable",
                "IntellaCmd.exe et/ou l'utilisateur ne sont pas renseignés : "
                "« Valider les opérations » ne pourra pas être lancé automatiquement "
                "à la fin de l'import.\n\nLancer l'import quand même ?")):
            return
        if not auto and not messagebox.askyesno(
            title, i18n.t(
                "import.run_confirm",
                "Lancer l'import dans Intella ?\n\n{b}\n\n"
                "IntellaCmd va ajouter les sources au cas (action non réversible "
                "côté cas). Une fenêtre de console s'ouvre et affiche la progression.\n\n"
                "« Valider les opérations » sera lancé automatiquement à la fin de l'import.\n\n"
                "Continuer ?", b=os.path.basename(bat))):
            return
        try:
            # Popen (et non os.startfile) : il faut le handle du processus pour
            # savoir QUAND l'import se termine et enchaîner sur la validation.
            # CREATE_NEW_CONSOLE conserve la console de progression d'IntellaCmd.
            # L'argument `auto` supprime la pause finale du .bat : sans lui, la
            # console attendait un clic et l'enchaînement restait suspendu.
            self._import_proc = subprocess.Popen(
                ["cmd", "/c", bat, json_builder.BAT_AUTO_FLAG],
                cwd=os.path.dirname(bat),
                creationflags=getattr(subprocess, "CREATE_NEW_CONSOLE", 0))
            self.app.log.log(i18n.t("import.launched_log", "Import lancé : {b}", b=bat))
        except OSError as exc:
            self._import_proc = None
            self.app.log.log(i18n.t(
                "import.launch_failed_log", "Échec du lancement de l'import : {e}", e=exc), level="ERROR")
            messagebox.showerror(title, i18n.t("import.launch_impossible", "Lancement impossible :\n{e}", e=exc))
            return
        self.btn_import.config(state="disabled")
        self.btn_run_all.config(state="disabled")
        self.after(1000, self._poll_import)

    def _poll_import(self):
        """Attend la fin du .bat puis enchaîne sur « Valider les opérations ».

        Le bouton « Valider les opérations » reste utile pour les scripts lancés
        à la main (hors application).
        """
        proc = self._import_proc
        if proc is None:
            return
        if proc.poll() is None:
            self.after(1000, self._poll_import)
            return
        self._import_proc = None
        self.btn_import.config(state="normal")
        self.btn_run_all.config(state="normal")
        if not self._auto_validate:
            self.app.log.log(i18n.t(
                "import.finished_no_validate_log",
                "Import terminé (code {c}) — validation automatique ignorée "
                "(IntellaCmd.exe ou utilisateur manquant).", c=proc.returncode))
            return
        self.app.log.log(i18n.t(
            "import.finished_log",
            "Import terminé (code {c}) — lancement automatique de « Valider les opérations ».",
            c=proc.returncode))
        self.valider_operations()

    # ------------------------------------------------------------------ #
    # Validation des opérations (re-scan du cas + analyse des logs)      #
    # ------------------------------------------------------------------ #
    def valider_operations(self):
        if self._compound_blocked():
            return
        title = i18n.t("import.validate", "Valider les opérations")
        meta = self.app.case_meta
        if not meta:
            messagebox.showinfo(title, i18n.t(
                "import.select_case_short", "Sélectionnez d'abord un cas (étape « 1. Le cas »)."))
            return
        exe = path_parser.clean_field(self.app.var_exe.get())
        user = self.app.var_user.get().strip()
        if not exe or not user:
            messagebox.showerror(title, i18n.t(
                "import.validate_requires", "IntellaCmd.exe et l'utilisateur sont requis."))
            return
        logs_dir = config.case_logs_dir(meta["name"])
        self.btn_validate.config(state="disabled")
        # Durée inconnue (re-scan IntellaCmd) → barre indéterminée, sans annulation
        # (interrompre un -exportSourceList en cours n'apporterait rien d'utile).
        self.size_bar.start_busy(i18n.t(
            "import.validate_busy", "Validation : re-scan du cas et analyse des logs…"))
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
        except Exception as exc:  # noqa: BLE001 — worker : rien ne doit mourir
            # ici sans repasser par le thread UI (IntellaCmd absent, licence,
            # XML illisible, journaux disparus). `_validate_error` remet le
            # bouton en état et journalise ; une exception nue tuerait le thread
            # en silence, bouton grisé pour de bon.
            self.after(0, self._validate_error, str(exc))

    def _validate_error(self, msg):
        self.btn_validate.config(state="normal")
        self.size_bar.stop()
        self.app.log.log(i18n.t("import.validate_rescan_failed_log", "Validation : échec du re-scan : {m}", m=msg),
                         level="ERROR")
        messagebox.showerror(i18n.t("import.validate", "Valider les opérations"), msg)

    def _validate_done(self, inventory, logs, run_dir=None):
        self.btn_validate.config(state="normal")
        self.size_bar.stop()
        existing = inventory["existing_paths"]
        # Index logs par chemin d'évidence (normalisé) pour le recoupement.
        log_by_path = {}
        for lg in logs:
            ev = lg.get("evidence")
            if ev:
                log_by_path[path_parser.normalize_path(ev).lower()] = lg

        rows = []
        # Chemins (tels que saisis) des sources confirmées dans le cas : sert à
        # persister les tailles. Indexé par CHEMIN et pas par nom — les noms sont
        # renommables au double-clic, donc non uniques.
        confirmed_paths = []
        if self.sources:
            for s in self.sources:
                key = path_parser.normalize_path(s.path).lower()
                in_case = key in existing
                lg = log_by_path.get(key)
                rows.append((s.name, in_case, lg))
                if in_case and (lg is None or lg["ok"]):
                    confirmed_paths.append(s.path)
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
        self._persist_measured_sizes(confirmed_paths)
        self._last_validation_ok = bool(confirmed_paths)
        self.app.update_steps()
        if confirmed_paths:
            self.app.set_status(i18n.t(
                "import.status_validated", "{n} source(s) confirmée(s) dans le cas.",
                n=len(confirmed_paths)))
        self._show_validation(inventory, logs, rows, run_dir, confirmed_paths)

    def _persist_measured_sizes(self, confirmed_paths):
        """Écrit dans IF_<cas>.info les tailles des sources CONFIRMÉES dans le cas.

        ``confirmed_paths`` : chemins (tels que saisis) des sources retrouvées
        dans le cas et sans erreur de log. Les autres (absentes, en échec)
        restent hors cache : leur contenu peut encore changer avant un nouvel
        import — elles seront remesurées.
        """
        meta = self.app.case_meta
        if not meta or not self._pending_sizes:
            return
        to_persist = {p: self._pending_sizes[p] for p in confirmed_paths
                      if p in self._pending_sizes}
        if not to_persist:
            return
        if case_info.update_folder_sizes(meta["folder"], meta["name"], to_persist):
            for path in to_persist:
                self._pending_sizes.pop(path, None)
            self.app.log.log(i18n.t(
                "import.sizes_persisted_log",
                "{n} taille(s) mémorisée(s) dans IF_<cas>.info (sources confirmées dans le cas).",
                n=len(to_persist)))

    def _show_validation(self, inventory, logs, rows, run_dir=None, confirmed_paths=None):
        win = make_dialog(self, i18n.t("import.validate", "Valider les opérations"),
                          "900x460")

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
        # Boucle du workflow sous-cas : ce qui est confirmé dans le cas n'a plus
        # rien à faire dans la liste d'import — ne reste que le reliquat à
        # réimporter (sous-cas manuel, sources en échec…). Bouton et non popup
        # automatique : c'est une modification de la liste, elle reste choisie.
        if confirmed_paths and self.sources:
            make_button(bar, i18n.t("import.drop_confirmed",
                                    "Retirer les sources confirmées de la liste"),
                        lambda: self._drop_confirmed(list(confirmed_paths), win),
                        color=config.ACTION_COLOR).pack(side="left", padx=8)

    def _drop_confirmed(self, confirmed_paths, win=None):
        """Retire de la liste les sources confirmées présentes dans le cas."""
        keys = {path_parser.normalize_path(p).lower() for p in confirmed_paths}
        restantes = [s for s in self.sources
                     if path_parser.normalize_path(s.path).lower() not in keys]
        retirees = len(self.sources) - len(restantes)
        if not retirees:
            return
        if not messagebox.askyesno(
            i18n.t("import.validate", "Valider les opérations"),
            i18n.t("import.drop_confirmed_ask",
                   "Retirer {n} source(s) confirmée(s) dans le cas de la liste "
                   "d'import ?\n\nIl restera {r} source(s) — celles à réimporter "
                   "(sous-cas, échecs).", n=retirees, r=len(restantes))):
            return
        self.sources = restantes
        self._sort_col = None
        self._refresh_tree()
        self.app.log.log(i18n.t(
            "import.drop_confirmed_log",
            "{n} source(s) confirmée(s) retirée(s) de la liste d'import.", n=retirees))
        if win is not None:
            win.destroy()

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
