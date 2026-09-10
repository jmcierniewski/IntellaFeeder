"""Onglet « Profils » : profils de paramètres d'analyse par source.

- Liste des profils (gauche) : ``défaut`` réservé + profils enregistrés dans le
  ``.ini`` (partagés entre cas).
- Formulaire **thématique** (droite, défilant) : une case/champ par option
  pilotable via ``-addSourcesFromJson`` (catalogue ``profile_catalog``).

Workflow : sélectionner un profil → le formulaire se remplit (cases cochées
automatiquement) ; éditer ; « Enregistrer » crée ou met à jour. « Nouveau » part
des défauts. Le profil affecté à chaque source se choisit dans le récapitulatif
de l'onglet Import (colonne « Profil »).
"""

import tkinter as tk
from tkinter import messagebox, simpledialog, ttk

import config
import i18n
import mime_catalog
import profile_catalog
import profile_translate
import profiles
from ui_category_picker import CategoryPicker
from ui_widgets import (Tooltip, make_button, mime_filter_summary,
                        settings_summary, show_mime_filter, show_source_settings)

# Unités d'option traduites via les clés i18n générales (unit.mb, unit.gb…).
_UNIT_KEYS = {"Mo": "unit.mb", "Go": "unit.gb"}

# Options rendues en zone de texte multi-ligne (valeurs très longues) plutôt
# qu'en champ d'une ligne — ex. le filtre de types MIME.
MULTILINE_KEYS = {"sourceTypeFilter"}

# Largeur (px) de la colonne des intitules du formulaire : la meme dans tous les
# groupes, pour que les champs s'alignent verticalement d'une section a l'autre.
LARGEUR_LIBELLE = 280

# Rouge du « Mode du filtre » : le seul réglage dont l'oubli inverse le sens de
# tout le filtre (défaut « exclude »).
MODE_WARN_COLOR = config.DANGER_COLOR


class ReferenceTab(ttk.Frame):
    """Sous-onglet « Référentiel » : état des descriptions de types MIME.

    🔴 **Il remplace un popup** (10/09/2026). L'ancien s'ouvrait à chaque lecture
    de cas pour annoncer « n types filtrés n'ont pas de description » — une
    information sur laquelle il n'y a **rien à faire** quand on a déjà la
    dernière version d'Intella, et qui coûtait un clic à chaque fois. Ici, elle
    est consultable quand on la cherche, **avec la liste** : sans les noms,
    l'utilisateur ne pouvait même pas juger si le manque le concernait.
    """

    def __init__(self, parent, app):
        super().__init__(parent)
        self.app = app

        self.lbl_state = ttk.Label(self, wraplength=900, justify="left")
        self.lbl_state.pack(anchor="w", padx=10, pady=(10, 4))

        self.lbl_case = ttk.Label(self, wraplength=900, justify="left")
        self.lbl_case.pack(anchor="w", padx=10, pady=(0, 6))

        holder = ttk.Frame(self)
        holder.pack(fill="both", expand=True, padx=10, pady=(0, 4))
        self.tree = ttk.Treeview(holder, columns=("name", "desc"),
                                 show="headings", height=8)
        self.tree.heading("name", text=i18n.t("profiles.ref_col", "Type sans description"))
        self.tree.heading("desc", text=i18n.t("profiles.ref_col_user", "Votre description"))
        self.tree.column("name", width=420, anchor="w")
        self.tree.column("desc", width=380, anchor="w")
        vsb = ttk.Scrollbar(holder, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=vsb.set)
        self.tree.pack(side="left", fill="both", expand=True)
        vsb.pack(side="right", fill="y")
        self.tree.tag_configure("user", foreground="#0f766e")
        # Double-clic = éditer. Le bouton dit la même chose pour qui ne devine
        # pas qu'une ligne de tableau puisse s'ouvrir.
        self.tree.bind("<Double-1>", lambda _e: self._editer())
        barre = ttk.Frame(self)
        barre.pack(fill="x", padx=10, pady=(0, 6))
        make_button(barre, i18n.t("profiles.ref_edit", "Décrire ce type…"),
                    self._editer).pack(side="left")
        ttk.Label(barre, foreground="#64748b", text=i18n.t(
            "profiles.ref_edit_hint",
            "(ou double-cliquez une ligne)")).pack(side="left", padx=8)

        ttk.Label(self, wraplength=900, justify="left", foreground="#64748b",
                  text=i18n.t(
                      "profiles.ref_hint",
                      "Un type sans description reste parfaitement utilisable : "
                      "seul son libellé manque. Ce sont le plus souvent des "
                      "synonymes qu'Intella écrit sans les nommer. Si votre "
                      "version d'Intella est plus récente que le référentiel, "
                      "vous pouvez l'actualiser depuis Maintenance → Types MIME.")
                  ).pack(anchor="w", padx=10, pady=(0, 10))
        self.refresh()

    def refresh(self):
        s = mime_catalog.stats()
        if s.get("external"):
            etat = i18n.t(
                "profiles.ref_external",
                "Descriptions : FICHIER EXTERNE ({n} entrées) — {p}",
                n=s["descriptions"], p=s.get("source", ""))
            couleur = "#1d4ed8"
        else:
            etat = i18n.t(
                "profiles.ref_builtin",
                "Descriptions : version intégrée à l'application ({n} entrées).",
                n=s["descriptions"])
            couleur = "#166534"
        if s.get("observed_learned"):
            etat += " " + i18n.t("profiles.ref_learned",
                                 "{n} nom(s) appris de vos cas.",
                                 n=s["observed_learned"])
        self.lbl_state.config(text=etat, foreground=couleur)

        # Les types du dernier cas SANS libellé, plus ceux qu'on a déjà décrits
        # soi-même : sans eux, on ne pourrait plus retrouver ni corriger une
        # description écrite pour un cas précédent.
        inedits = list(getattr(self.app, "undescribed_types", []) or [])
        miens = [n for n in mime_catalog.user_labels() if n not in inedits]
        lignes = inedits + sorted(miens)
        self.tree.delete(*self.tree.get_children())
        self._iids = {}
        for i, nom in enumerate(lignes):
            perso = mime_catalog.user_label(nom)
            iid = f"r{i}"          # nom potentiellement vide → jamais comme iid
            self._iids[iid] = nom
            self.tree.insert("", "end", iid=iid,
                             tags=("user",) if perso else (),
                             values=(nom or i18n.t("mime.untyped", "(sans type)"),
                                     perso))
        if not inedits:
            self.lbl_case.config(text=i18n.t(
                "profiles.ref_case_ok",
                "Aucun type sans description dans le dernier cas lu."),
                foreground="#166534")
        else:
            self.lbl_case.config(text=i18n.t(
                "profiles.ref_case",
                "{n} type(s) filtré(s) par le dernier cas lu n'ont pas de "
                "description :", n=len(inedits)), foreground="#475569")

    def _editer(self):
        """Saisit la description d'un type que Vound ne nomme pas."""
        sel = self.tree.selection()
        titre = i18n.t("profiles.ref_edit_title", "Décrire un type")
        if not sel:
            messagebox.showinfo(titre, i18n.t(
                "profiles.ref_edit_none", "Sélectionnez d'abord un type."))
            return
        nom = self._iids.get(sel[0], "")
        actuel = mime_catalog.user_label(nom)
        officiel = mime_catalog.label(nom) if not actuel else None
        invite = i18n.t("profiles.ref_edit_prompt",
                        "Description de « {n} » :", n=nom or "(sans type)")
        if officiel:
            # Le cas se produit si Intella a fini par nommer ce type : autant le
            # dire, plutôt que de laisser saisir un texte qui ne s'affichera pas.
            invite += "\n\n" + i18n.t(
                "profiles.ref_edit_official",
                "Attention : Intella décrit désormais ce type « {d} ». Sa "
                "description restera prioritaire sur la vôtre.", d=officiel)
        texte = simpledialog.askstring(titre, invite, initialvalue=actuel, parent=self)
        if texte is None:
            return
        try:
            mime_catalog.set_user_label(nom, texte)
        except OSError as exc:
            messagebox.showerror(titre, i18n.t(
                "profiles.ref_edit_failed",
                "Impossible d'enregistrer : {e}", e=exc))
            return
        self.app.log.log(i18n.t(
            "profiles.ref_edit_log", "Description personnelle : {n} → « {d} »",
            n=nom or "(sans type)", d=texte.strip() or "—"))
        self.refresh()


class ProfilesTab(ttk.Frame):
    def __init__(self, parent, app):
        super().__init__(parent)
        self.app = app
        self.vars = {}            # clé option -> tk.Variable (widgets simples)
        self._widgets = {}        # clé option -> widget (pour activer/désactiver)
        self._text_widgets = {}   # clé option -> tk.Text (multi-ligne)
        self._names = []          # identifiants des profils, dans l'ordre de la liste
        self.tooltip = Tooltip(self)
        self._build()
        # Ouvre sur le profil marqué par défaut, pas sur un formulaire vierge :
        # voir son nom étoilé dans la liste mais les réglages d'Intella dans le
        # formulaire donnait l'impression que le choix n'était pas pris (retour
        # utilisateur du 08/09/2026).
        self._refresh_list(select=self._default_profile())
        self._on_select()

    # ------------------------------------------------------------------ #
    def _build(self):
        intro = ttk.Label(
            self, padding=(10, 8, 10, 0), foreground="#475569", wraplength=1000,
            justify="left",
            text=i18n.t(
                "profiles.intro",
                "Un profil = jeu de paramètres d'analyse appliqué à une source à "
                "l'import (affecté dans l'onglet « 2. Import », colonne « Profil »). "
                "« Défaut Intella » applique les réglages standard d'Intella (aucune "
                "option forcée) ; seules les valeurs qui en diffèrent sont "
                "enregistrées et émises. L'étoile ★ marque le profil donné aux "
                "nouvelles sources — « Définir par défaut » le change."))
        intro.pack(fill="x")

        body = ttk.Frame(self)
        body.pack(fill="both", expand=True, padx=8, pady=8)
        body.columnconfigure(1, weight=1)
        body.rowconfigure(0, weight=1)

        # --- Colonne gauche : liste + actions sur les profils --- #
        left = ttk.LabelFrame(body, text=i18n.t("profiles.saved", "Profils enregistrés"))
        left.grid(row=0, column=0, sticky="nsw", padx=(0, 8))
        self.listbox = tk.Listbox(left, width=24, exportselection=False)
        self.listbox.pack(fill="y", expand=True, padx=6, pady=6)
        self.listbox.bind("<<ListboxSelect>>", lambda _e: self._on_select())

        ttk.Label(left, text=i18n.t("profiles.name_label", "Nom du profil")).pack(anchor="w", padx=6)
        self.var_name = tk.StringVar()
        ttk.Entry(left, textvariable=self.var_name).pack(fill="x", padx=6, pady=(0, 6))

        btns = ttk.Frame(left)
        btns.pack(fill="x", padx=6, pady=(0, 6))
        make_button(btns, i18n.t("profiles.new", "Nouveau"), self._new).pack(fill="x", pady=1)
        make_button(btns, i18n.t("profiles.duplicate", "Dupliquer…"),
                    self._duplicate).pack(fill="x", pady=1)
        make_button(btns, i18n.t("profiles.set_default", "★ Définir par défaut"),
                    self._set_default).pack(fill="x", pady=1)
        make_button(btns, i18n.t("common.save", "Enregistrer"), self._save,
                   color=config.ACTION_COLOR).pack(fill="x", pady=1)
        make_button(btns, i18n.t("profiles.rename", "Renommer…"), self._rename).pack(fill="x", pady=1)
        make_button(btns, i18n.t("common.delete", "Supprimer"), self._delete,
                   color=config.DANGER_COLOR).pack(fill="x", pady=1)

        # --- Colonne droite : commentaires + formulaire thématique défilant --- #
        rightcol = ttk.Frame(body)
        rightcol.grid(row=0, column=1, sticky="nsew")
        rightcol.columnconfigure(0, weight=1)
        rightcol.rowconfigure(1, weight=1)

        # Commentaires (multi-ligne), AVANT les options d'analyse.
        cbox = ttk.LabelFrame(rightcol, text=i18n.t("profiles.comments", "Commentaires"))
        cbox.grid(row=0, column=0, sticky="ew", pady=(0, 6))
        cbox.columnconfigure(0, weight=1)
        self.txt_comment = tk.Text(cbox, height=3, wrap="word", undo=True)
        cvsb = ttk.Scrollbar(cbox, orient="vertical", command=self.txt_comment.yview)
        self.txt_comment.configure(yscrollcommand=cvsb.set)
        self.txt_comment.grid(row=0, column=0, sticky="ew", padx=(6, 0), pady=6)
        cvsb.grid(row=0, column=1, sticky="ns", pady=6)

        # « Voir les réglages » : déplacé de l'Inventaire vers ici le 10/09/2026.
        # Il parle du PROFIL (ce qu'il rejoue, ce qui reste à refaire dans
        # Intella), pas de l'inventaire du cas — il était rangé au mauvais
        # endroit, sur le chemin de l'import qui doit rester dégagé.
        self.btn_settings = make_button(
            cbox, i18n.t("profiles.view_settings", "Voir les réglages de la source…"),
            self._show_source_settings)
        self.btn_settings.grid(row=1, column=0, columnspan=2, sticky="w",
                               padx=6, pady=(0, 6))
        self.lbl_settings = ttk.Label(cbox, foreground="#64748b", wraplength=700,
                                      justify="left")
        self.lbl_settings.grid(row=2, column=0, columnspan=2, sticky="w",
                               padx=6, pady=(0, 6))
        self._refresh_source_settings()

        # Sous-onglets : le formulaire d'options, et le sélecteur de catégories
        # (deux façons de remplir le MÊME profil — la liste de gauche et les
        # boutons restent communs, sinon on perdrait le fil de ce qu'on édite).
        subnb = ttk.Notebook(rightcol)
        self.subnotebook = subnb
        subnb.grid(row=1, column=0, sticky="nsew")

        right = ttk.LabelFrame(subnb, text=i18n.t("profiles.analysis_options", "Options d'analyse"))
        right.rowconfigure(0, weight=1)
        right.columnconfigure(0, weight=1)
        canvas = tk.Canvas(right, highlightthickness=0)
        vsb = ttk.Scrollbar(right, orient="vertical", command=canvas.yview)
        canvas.configure(yscrollcommand=vsb.set)
        canvas.grid(row=0, column=0, sticky="nsew")
        vsb.grid(row=0, column=1, sticky="ns")
        form = ttk.Frame(canvas)
        win = canvas.create_window((0, 0), window=form, anchor="nw")
        form.bind("<Configure>", lambda _e: canvas.configure(scrollregion=canvas.bbox("all")))
        canvas.bind("<Configure>", lambda e: canvas.itemconfigure(win, width=e.width))
        # Molette active seulement quand le pointeur survole ce formulaire (sinon
        # bind_all capterait la molette des autres onglets).
        def _wheel(e):
            canvas.yview_scroll(int(-e.delta / 120), "units")
        canvas.bind("<Enter>", lambda _e: canvas.bind_all("<MouseWheel>", _wheel))
        canvas.bind("<Leave>", lambda _e: canvas.unbind_all("<MouseWheel>"))

        self._build_form(form)

        self.picker = CategoryPicker(
            subnb, self.app,
            get_filter=lambda: self._get_option("sourceTypeFilter"),
            get_mode=self._filter_mode,
            set_filter=self._set_filter_from_picker)
        subnb.add(right, text=" " + i18n.t("profiles.tab_options", "Réglages"))
        subnb.add(self.picker, text=" " + i18n.t("profiles.tab_types",
                                                 "Types de fichiers à indexer"))
        self.reference = ReferenceTab(subnb, self.app)
        subnb.add(self.reference, text=" " + i18n.t("profiles.tab_reference",
                                                    "Référentiel"))

    def refresh_reference(self):
        """Rafraîchit le sous-onglet « Référentiel » (appelé par l'Inventaire)."""
        if hasattr(self, "reference"):
            self.reference.refresh()

    def _set_filter_from_picker(self, filtre: str, mode: str):
        """Écrit ce que le sélecteur a composé — le profil reste à enregistrer.

        Volontairement **sans sauvegarde automatique** : le sélecteur remplit le
        formulaire comme le ferait une saisie, et « Enregistrer » garde son rôle
        de point de validation unique.
        """
        self._set_option("sourceTypeFilter", filtre)
        self._set_option("sourceTypeFilterMode", mode)
        self._refresh_mime_summary()

    def _build_form(self, form):
        for group, opts in profile_catalog.GROUPS:
            group_key = profile_catalog.GROUP_KEYS.get(group, "")
            box = ttk.LabelFrame(form, text=i18n.t(group_key, group))
            box.pack(fill="x", expand=True, padx=6, pady=4)
            # Intitules alignes d'un groupe a l'autre : sans `minsize`, chaque
            # LabelFrame calait sa colonne 0 sur son plus long libelle, donc les
            # champs repartaient d'une abscisse differente a chaque section.
            box.columnconfigure(0, minsize=LARGEUR_LIBELLE)
            box.columnconfigure(1, weight=1)
            gr = 0  # ligne de grille courante (un multi-ligne en consomme 2)
            for o in opts:
                key = o["key"]
                label = i18n.t(o["label_key"], o["label"])
                if o.get("unit"):
                    unit = i18n.t(_UNIT_KEYS.get(o["unit"], ""), o["unit"])
                    label += f" ({unit})"
                if not o["confirmed"]:
                    label += "  — " + i18n.t("profiles.to_verify", "à éprouver")
                if o["applies"] == "image":
                    label += "  " + i18n.t("profiles.images_only", "[images]")
                if o["type"] == "bool":
                    var = tk.BooleanVar(value=bool(o["default"]))
                    w = ttk.Checkbutton(box, variable=var, text=label)
                    w.grid(row=gr, column=0, columnspan=2, sticky="w", padx=6, pady=2)
                    self.vars[key] = var
                    self._widgets[key] = w
                    gr += 1
                elif o["type"] == "str" and key in MULTILINE_KEYS:
                    # Valeur très longue (ex. filtre MIME) : zone multi-ligne qui
                    # s'agrandit au clic pour copier/coller facilement.
                    ttk.Label(box, text=label).grid(row=gr, column=0, columnspan=2,
                                                    sticky="w", padx=6, pady=(2, 0))
                    w = tk.Text(box, height=2, wrap="word", undo=True)
                    w.grid(row=gr + 1, column=0, columnspan=2, sticky="ew", padx=6, pady=(0, 2))
                    w.bind("<FocusIn>", lambda _e, t=w: t.configure(height=10))
                    w.bind("<FocusOut>", lambda _e, t=w: t.configure(height=2))
                    self._text_widgets[key] = w
                    self._widgets[key] = w
                    gr += 2
                    if key == "sourceTypeFilter":
                        # Un « refine » complet dans Intella produit 600 noms
                        # séparés par des virgules : illisible dans un champ.
                        gr += self._add_mime_reader(box, gr, w)
                else:
                    lbl = ttk.Label(box, text=label)
                    if key == "sourceTypeFilterMode":
                        # 🔴 GRAS ET ROUGE, demandé le 10/09/2026. Le défaut est
                        # « exclude » : une liste saisie comme « ce que je veux »
                        # ferait alors exactement l'inverse — indexer tout SAUF
                        # ça. L'erreur ne se voit qu'après l'import, et Intella
                        # ne permet pas de revoir les réglages d'une source.
                        lbl.configure(foreground=MODE_WARN_COLOR,
                                      font=("Segoe UI", 9, "bold"))
                    lbl.grid(row=gr, column=0, sticky="w", padx=6, pady=2)
                    var = tk.StringVar(value=str(o["default"]))
                    # Une liste deroulante ou un compteur n'a pas besoin de
                    # 1 400 px pour afficher vingt caracteres : `sticky="w"` les
                    # laisse a leur largeur utile. Seuls les champs de texte
                    # libre (chemins, filtres) s'etirent.
                    if o["type"] == "enum":
                        # PAS `readonly` : le domaine d'une valeur peut etre plus
                        # large que ce qu'on connait (constate sur `splitMode`,
                        # dont l'interface d'Intella propose plus que l'aide CLI).
                        # Interdire la saisie fermerait la porte a une version
                        # future sans rien gagner.
                        w = ttk.Combobox(box, textvariable=var, values=o["choices"],
                                         width=30)
                        colle = "w"
                    elif o["type"] == "int":
                        w = ttk.Spinbox(box, textvariable=var, from_=0, to=10_000_000, width=12)
                        colle = "w"
                    else:
                        w = ttk.Entry(box, textvariable=var)
                        colle = "ew"
                    w.grid(row=gr, column=1, sticky=colle, padx=6, pady=2)
                    if key == "fileNameFilters":
                        self._attach_tip(w, i18n.t(
                            "profiles.filename_filter_tip",
                            "Jokers autorisés dans les noms de fichiers : "
                            "« ? » (un caractère) et « * » (plusieurs). "
                            "Ex. : rapport_*.pdf, IMG_????.jpg"))
                    self.vars[key] = var
                    self._widgets[key] = w
                    gr += 1
        # Le mode du filtre est créé APRÈS le champ de filtre (ordre du
        # catalogue) : on ne peut l'écouter qu'ici, formulaire complet.
        if "sourceTypeFilterMode" in self.vars:
            self.vars["sourceTypeFilterMode"].trace_add(
                "write", lambda *_a: self._refresh_mime_summary())

    def _add_mime_reader(self, box, row, text_widget) -> int:
        """Résumé du filtre de types + bouton de lecture. Retourne les lignes prises.

        Le résumé se met à jour à la frappe : sans lui, rien ne dirait que le
        champ contient 600 entrées plutôt que 3, ni qu'un nom n'a jamais été vu.
        """
        ligne = ttk.Frame(box)
        ligne.grid(row=row, column=0, columnspan=2, sticky="ew", padx=6, pady=(0, 4))
        self.lbl_mime = ttk.Label(ligne, text=mime_filter_summary(""))
        self.lbl_mime.pack(side="left")
        make_button(ligne, i18n.t("profiles.mime_view", "Voir les types…"),
                    self._show_mime_filter).pack(side="right")
        text_widget.bind("<<Modified>>", self._on_mime_modified)
        return 1

    def _on_mime_modified(self, event):
        # Tk n'émet `<<Modified>>` qu'une fois tant que le drapeau n'est pas
        # remis à zéro : l'oublier fige le résumé après la première frappe.
        widget = event.widget
        widget.edit_modified(False)
        self._refresh_mime_summary()

    def _refresh_mime_summary(self):
        if not hasattr(self, "lbl_mime"):
            return
        self.lbl_mime.config(text=mime_filter_summary(
            self._get_option("sourceTypeFilter"), self._filter_mode()))

    def _filter_mode(self) -> str:
        """Mode courant du filtre — sans lui, la liste se lit à l'envers."""
        try:
            return self._get_option("sourceTypeFilterMode")
        except KeyError:
            return ""

    def _show_mime_filter(self):
        show_mime_filter(self, self._get_option("sourceTypeFilter"),
                         i18n.t("profiles.mime_title", "Types filtrés par ce profil"),
                         self._filter_mode(),
                         on_change=self._set_filter_text)

    def _set_filter_text(self, texte: str):
        """Réécrit le champ de filtre depuis la fenêtre de lecture/composition."""
        self._set_option("sourceTypeFilter", texte)
        self._refresh_mime_summary()
        if hasattr(self, "picker"):
            self.picker.refresh()

    # ------------------------------------------------------------------ #
    # Réglages de la source d'origine (« Info Profil »)                  #
    # ------------------------------------------------------------------ #
    def _refresh_source_settings(self):
        """Active le bouton seulement si un profil vient d'une source lue.

        Un profil saisi à la main n'a pas de source d'origine : proposer le
        bouton quand même donnerait une fenêtre vide, et laisserait croire que
        la fonction est en panne.
        """
        src = getattr(self, "_source_xml", None)
        self.btn_settings.config(state="normal" if src else "disabled")
        if src:
            self.lbl_settings.config(text=i18n.t(
                "profiles.settings_from",
                "Réglages repris de la source « {n} ». {r}",
                n=src.get("name") or "?", r=settings_summary(src)))
        else:
            self.lbl_settings.config(text=i18n.t(
                "profiles.settings_none",
                "Pour voir ce qu'un profil reprend d'une source réglée dans "
                "Intella : onglet « Inventaire du cas », sélectionnez la source, "
                "« Info Profil → »."))

    def _show_source_settings(self):
        src = getattr(self, "_source_xml", None)
        if not src:
            return
        show_source_settings(self, src, i18n.t(
            "profiles.settings_title", "Réglages de « {n} »",
            n=src.get("name") or "?"))

    def _attach_tip(self, widget, text):
        widget.bind("<Enter>", lambda e: self.tooltip.show(text, e.x_root + 12, e.y_root + 20))
        widget.bind("<Leave>", lambda _e: self.tooltip.hide())

    # ------------------------------------------------------------------ #
    # Liste / sélection                                                  #
    # ------------------------------------------------------------------ #
    def _refresh_list(self, select: str = None):
        # `_names` garde les identifiants techniques dans l'ordre de la liste :
        # ce qui est AFFICHÉ peut différer (« Défaut Intella »), mais tout le
        # reste du code — .ini, listes exportées, colonne « Profil » — travaille
        # sur l'identifiant.
        self._names = profiles.list_names()
        defaut = self._default_profile()
        self.listbox.delete(0, "end")
        for n in self._names:
            # ★ : le profil donné aux nouvelles sources. Sans repère dans la
            # liste, le réglage était invisible (retour utilisateur du 08/09).
            marque = "★ " if n == defaut else "    "
            self.listbox.insert("end", marque + profiles.display_name(n))
        if select and select in self._names:
            i = self._names.index(select)
            self.listbox.selection_clear(0, "end")
            self.listbox.selection_set(i)
            self.listbox.see(i)

    def _selected_name(self):
        sel = self.listbox.curselection()
        return self._names[sel[0]] if sel and sel[0] < len(self._names) else None

    def _on_select(self):
        name = self._selected_name()
        if not name:
            return
        self.var_name.set("" if name == profiles.DEFAULT_NAME else name)
        self._load_values(profiles.get_values(name))
        self._set_comment(profiles.get_comment(name))
        self._set_form_state(name != profiles.DEFAULT_NAME)
        # On change de profil : les réglages de la source affichée ne sont plus
        # ceux de celui-ci. Les garder ferait lire le tableau du mauvais profil.
        self._source_xml = None
        self._refresh_source_settings()

    def _set_form_state(self, editable: bool):
        state = "normal" if editable else "disabled"
        for key, w in self._widgets.items():
            # Combobox éditable seulement quand actif ; sinon désactivé.
            w.configure(state=state if not isinstance(w, ttk.Combobox)
                        else ("readonly" if editable else "disabled"))
        self.txt_comment.configure(state=state)

    # ------------------------------------------------------------------ #
    # Lecture / écriture du formulaire                                   #
    # ------------------------------------------------------------------ #
    def _set_option(self, key, value):
        if key in self._text_widgets:
            t = self._text_widgets[key]
            t.configure(state="normal")   # écriture ignorée si état 'disabled'
            t.delete("1.0", "end")
            t.insert("1.0", "" if value is None else str(value))
        elif key in self.vars:
            self.vars[key].set(value)

    def _get_option(self, key):
        if key in self._text_widgets:
            return self._text_widgets[key].get("1.0", "end-1c").strip()
        return self.vars[key].get()

    def _load_values(self, values: dict):
        for key in self._widgets:
            if key in values:
                self._set_option(key, values[key])
        self._refresh_mime_summary()
        # Le sélecteur montre le filtre du profil affiché : sans ce rappel, il
        # garderait les cases du profil précédent.
        if hasattr(self, "picker"):
            self.picker.refresh()

    def _collect_values(self) -> dict:
        return {key: profile_catalog.coerce(key, self._get_option(key))
                for key in self._widgets}

    def _set_comment(self, text: str):
        self.txt_comment.configure(state="normal")
        self.txt_comment.delete("1.0", "end")
        self.txt_comment.insert("1.0", text or "")

    def _get_comment(self) -> str:
        return self.txt_comment.get("1.0", "end-1c").strip()

    # ------------------------------------------------------------------ #
    # Actions                                                            #
    # ------------------------------------------------------------------ #
    def _new(self):
        self.listbox.selection_clear(0, "end")
        self.var_name.set("")
        self._load_values(profile_catalog.default_values())
        self._set_comment("")
        self._set_form_state(True)

    def _default_profile(self) -> str:
        """Identifiant du profil donné aux nouvelles sources (mémorisé au .ini)."""
        nom = self.app.settings.get("default_profile", profiles.DEFAULT_NAME)
        return nom if profiles.exists(nom) else profiles.DEFAULT_NAME

    def _set_default(self):
        """Déclare le profil sélectionné « par défaut » pour les nouvelles sources.

        Le réglage existait déjà (combo de l'onglet Import) mais **ne se voyait
        pas** : c'est ici qu'on le cherche, à côté des profils. Écrit tout de
        suite au `.ini` — un réglage qu'on ne retrouve pas au redémarrage passe
        pour n'avoir pas été pris.
        """
        titre = i18n.t("profiles.set_default_title", "Profil par défaut")
        nom = self._selected_name()
        if not nom:
            messagebox.showinfo(titre, i18n.t(
                "profiles.select_first", "Sélectionnez d'abord un profil."))
            return
        self.app.settings.set("default_profile", nom)
        self.app.settings.save()
        self._refresh_list(select=nom)
        # L'onglet Import affiche le même réglage : il doit suivre sans attendre
        # un redémarrage.
        tab = getattr(self.app, "import_tab", None)
        if tab is not None and hasattr(tab, "cb_default_profile"):
            tab.cb_default_profile.set(profiles.display_name(nom))
        self.app.log.log(i18n.t(
            "profiles.set_default_log",
            "Profil par défaut des nouvelles sources : « {n} ».",
            n=profiles.display_name(nom)))
        messagebox.showinfo(titre, i18n.t(
            "profiles.set_default_msg",
            "« {n} » sera appliqué aux nouvelles sources analysées.\n\n"
            "Les sources déjà listées gardent le leur ; la colonne « Profil » "
            "de l'onglet Import permet de les changer une à une.",
            n=profiles.display_name(nom)))

    def _duplicate(self):
        """Copie le profil sélectionné sous un autre nom, puis l'ouvre.

        Marche aussi depuis « Défaut Intella » : on obtient alors un profil
        modifiable partant des réglages d'Intella — c'est le point de départ le
        plus courant, et il n'existait pas.
        """
        titre = i18n.t("profiles.duplicate_title", "Dupliquer le profil")
        source = self._selected_name()
        if not source:
            messagebox.showinfo(titre, i18n.t(
                "profiles.select_first", "Sélectionnez d'abord un profil."))
            return
        propose = i18n.t("profiles.copy_suffix", "{n} (copie)",
                         n=profiles.display_name(source))
        cible = simpledialog.askstring(
            titre, i18n.t("profiles.duplicate_prompt",
                          "Nom du nouveau profil (copie de « {n} ») :",
                          n=profiles.display_name(source)),
            initialvalue=propose, parent=self)
        if not cible:
            return
        try:
            profiles.duplicate_profile(source, cible.strip())
        except ValueError as exc:
            messagebox.showerror(titre, str(exc))
            return
        self._refresh_list(select=cible.strip())
        self._on_select()
        self.app.log.log(i18n.t("profiles.duplicate_log",
                                "Profil « {s} » dupliqué en « {n} ».",
                                s=profiles.display_name(source), n=cible.strip()))

    def load_from_values(self, values: dict, suggested_name: str = "", src: dict = None):
        """Pré-remplit le formulaire avec ``values`` (fusionnés sur les défauts) en
        tant que **nouveau profil non enregistré**. Utilisé par « Info Profil ».

        ``src`` : la source de l'export dont viennent ces valeurs. Gardée pour
        « Voir les réglages… », qui dit ce que le profil **ne** reprend pas.
        """
        self.listbox.selection_clear(0, "end")
        merged = profile_catalog.default_values()
        for k, v in (values or {}).items():
            if k in merged:
                merged[k] = profile_catalog.coerce(k, v)
        self._load_values(merged)
        self._set_comment(self._provenance_comment(src))
        self._set_form_state(True)
        self.var_name.set(suggested_name or "")
        self._source_xml = src
        self._refresh_source_settings()

    @staticmethod
    def _provenance_comment(src: dict) -> str:
        """Commentaire pré-rempli : d'où vient le profil, et ce qu'il ne rejoue pas.

        Le champ restait vide, si bien que la provenance était perdue dès
        l'enregistrement — or c'est la seule information qu'on veuille retrouver
        en rouvrant un profil trois mois plus tard. Éditable, comme tout
        commentaire.
        """
        if not src:
            return ""
        lignes = [i18n.t(
            "profiles.provenance",
            "Repris de la source « {n} » le {d}.",
            n=src.get("name") or "?", d=config.now_str("%d/%m/%Y"))]
        perdus = profile_translate.unsupported_keys(src)
        if perdus:
            lignes.append(i18n.t(
                "profiles.provenance_lost",
                "Non rejoué (à refaire dans Intella) : {k}", k=", ".join(perdus)))
        return "\n".join(lignes)

    def _save(self):
        title = i18n.t("common.save", "Enregistrer")
        name = self.var_name.get().strip()
        if not name:
            messagebox.showerror(title, i18n.t("profiles.name_required", "Indiquez un nom de profil."))
            return
        if name == profiles.DEFAULT_NAME:
            messagebox.showerror(title, i18n.t("profiles.default_reserved",
                                               "Le profil « défaut » est réservé."))
            return
        if profiles.exists(name) and not messagebox.askyesno(
                title, i18n.t("profiles.overwrite_confirm",
                              "Le profil « {n} » existe déjà. Le mettre à jour ?", n=name)):
            return
        try:
            profiles.save_profile(name, self._collect_values(), self._get_comment())
        except ValueError as exc:
            messagebox.showerror(title, str(exc))
            return
        self._refresh_list(select=name)
        self.app.log.log(i18n.t("profiles.saved_log", "Profil enregistré : « {n} ».", n=name))
        messagebox.showinfo(title, i18n.t("profiles.saved_msg", "Profil « {n} » enregistré.", n=name))

    def _rename(self):
        title = i18n.t("profiles.rename", "Renommer…")
        name = self._selected_name()
        if not name or name == profiles.DEFAULT_NAME:
            messagebox.showinfo(title, i18n.t("profiles.select_non_default",
                                              "Sélectionnez un profil (≠ « défaut »)."))
            return
        new = simpledialog.askstring(
            i18n.t("profiles.rename_title", "Renommer le profil"),
            i18n.t("profiles.new_name", "Nouveau nom :"),
            initialvalue=name, parent=self)
        if not new:
            return
        try:
            profiles.rename_profile(name, new.strip())
        except ValueError as exc:
            messagebox.showerror(title, str(exc))
            return
        self._refresh_list(select=new.strip())
        self._on_select()
        self.app.log.log(i18n.t(
            "profiles.renamed_log", "Profil renommé : « {o} » → « {n} ».", o=name, n=new.strip()))

    def _delete(self):
        title = i18n.t("common.delete", "Supprimer")
        name = self._selected_name()
        if not name or name == profiles.DEFAULT_NAME:
            messagebox.showinfo(title, i18n.t("profiles.select_non_default",
                                              "Sélectionnez un profil (≠ « défaut »)."))
            return
        if not messagebox.askyesno(title, i18n.t(
                "profiles.delete_confirm", "Supprimer le profil « {n} » ?", n=name)):
            return
        try:
            profiles.delete_profile(name)
        except ValueError as exc:
            messagebox.showerror(title, str(exc))
            return
        self._refresh_list()
        self._new()
        self.app.log.log(i18n.t("profiles.deleted_log", "Profil supprimé : « {n} ».", n=name))
