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

import i18n
import profile_catalog
import profiles
from ui_widgets import Tooltip, make_button

# Unités d'option traduites via les clés i18n générales (unit.mb, unit.gb…).
_UNIT_KEYS = {"Mo": "unit.mb", "Go": "unit.gb"}

# Options rendues en zone de texte multi-ligne (valeurs très longues) plutôt
# qu'en champ d'une ligne — ex. le filtre de types MIME.
MULTILINE_KEYS = {"sourceTypeFilter"}


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
                   color="#16a34a").pack(fill="x", pady=1)
        make_button(btns, i18n.t("profiles.rename", "Renommer…"), self._rename).pack(fill="x", pady=1)
        make_button(btns, i18n.t("common.delete", "Supprimer"), self._delete,
                   color="#b91c1c").pack(fill="x", pady=1)

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

        right = ttk.LabelFrame(rightcol, text=i18n.t("profiles.analysis_options", "Options d'analyse"))
        right.grid(row=1, column=0, sticky="nsew")
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

    def _build_form(self, form):
        for group, opts in profile_catalog.GROUPS:
            group_key = profile_catalog.GROUP_KEYS.get(group, "")
            box = ttk.LabelFrame(form, text=i18n.t(group_key, group))
            box.pack(fill="x", expand=True, padx=6, pady=4)
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
                else:
                    ttk.Label(box, text=label).grid(row=gr, column=0, sticky="w", padx=6, pady=2)
                    var = tk.StringVar(value=str(o["default"]))
                    if o["type"] == "enum":
                        w = ttk.Combobox(box, textvariable=var, values=o["choices"], width=28)
                    elif o["type"] == "int":
                        w = ttk.Spinbox(box, textvariable=var, from_=0, to=10_000_000, width=12)
                    else:
                        w = ttk.Entry(box, textvariable=var)
                    w.grid(row=gr, column=1, sticky="ew", padx=6, pady=2)
                    if key == "fileNameFilters":
                        self._attach_tip(w, i18n.t(
                            "profiles.filename_filter_tip",
                            "Jokers autorisés dans les noms de fichiers : "
                            "« ? » (un caractère) et « * » (plusieurs). "
                            "Ex. : rapport_*.pdf, IMG_????.jpg"))
                    self.vars[key] = var
                    self._widgets[key] = w
                    gr += 1

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

    def load_from_values(self, values: dict, suggested_name: str = ""):
        """Pré-remplit le formulaire avec ``values`` (fusionnés sur les défauts) en
        tant que **nouveau profil non enregistré**. Utilisé par « Info Profil ».
        """
        self.listbox.selection_clear(0, "end")
        merged = profile_catalog.default_values()
        for k, v in (values or {}).items():
            if k in merged:
                merged[k] = profile_catalog.coerce(k, v)
        self._load_values(merged)
        self._set_comment("")
        self._set_form_state(True)
        self.var_name.set(suggested_name or "")

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
