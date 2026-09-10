"""Sélecteur de **catégories de fichiers** pour composer un filtre de source.

Pourquoi ce sélecteur existe : dans Intella on coche le peu qu'on veut, et
l'export enregistre **tout le reste** — éditer un filtre à la main reviendrait à
taper ce dont on ne veut pas, par centaines. Le mode ``include``, éprouvé en
réel le 09/09/2026, permet enfin de dire ce qu'on **veut**.

⚠ **Mode `include` uniquement, et ce n'est pas un détail de confort.** En
include, une lacune du référentiel est **inoffensive** : un type que nous ne
connaissons pas n'est pas coché, donc pas indexé — c'est exactement ce qu'un
include signifie. En exclude, la même lacune ferait indexer un type à l'insu de
l'utilisateur, et Intella ne permet pas de revoir les réglages après import.
Le sélecteur n'écrit donc **jamais** de filtre en mode exclude.

Il travaille au grain de la **catégorie** (78 entrées, toutes décrites, toutes
vues dans des filtres réels) et non du type (~600, dont 121 alias sans libellé).
"""

import tkinter as tk
from tkinter import messagebox, ttk

import config
import i18n
import mime_catalog
from ui_widgets import make_button

COLONNES = 3


class CategoryPicker(ttk.Frame):
    """Grille de cases à cocher + application au profil courant.

    ``get_filter`` / ``get_mode`` lisent l'état du formulaire, ``set_filter``
    l'écrit : le sélecteur ne possède rien, il propose une autre façon de
    remplir le même champ.
    """

    def __init__(self, parent, app, get_filter, get_mode, set_filter):
        super().__init__(parent)
        self.app = app
        self._get_filter = get_filter
        self._get_mode = get_mode
        self._set_filter = set_filter
        self.vars: dict[str, tk.BooleanVar] = {}

        self.lbl_state = ttk.Label(self, wraplength=980, justify="left")
        self.lbl_state.pack(fill="x", padx=10, pady=(10, 6))

        bar = ttk.Frame(self)
        bar.pack(fill="x", padx=10, pady=(0, 6))
        make_button(bar, i18n.t("picker.apply", "Appliquer au profil"),
                    self._apply, color=config.ACTION_COLOR).pack(side="left")
        make_button(bar, i18n.t("picker.reload", "Relire le profil"),
                    self.refresh).pack(side="left", padx=6)
        make_button(bar, i18n.t("picker.none", "Tout décocher"),
                    lambda: self._set_all(False)).pack(side="right")
        make_button(bar, i18n.t("picker.all", "Tout cocher"),
                    lambda: self._set_all(True)).pack(side="right", padx=6)

        self.lbl_count = ttk.Label(self, foreground="#475569")
        self.lbl_count.pack(fill="x", padx=10, pady=(0, 4))

        holder = ttk.Frame(self)
        holder.pack(fill="both", expand=True, padx=10, pady=(0, 10))
        canvas = tk.Canvas(holder, highlightthickness=0)
        vsb = ttk.Scrollbar(holder, orient="vertical", command=canvas.yview)
        canvas.configure(yscrollcommand=vsb.set)
        canvas.pack(side="left", fill="both", expand=True)
        vsb.pack(side="right", fill="y")
        self.grille = ttk.Frame(canvas)
        win = canvas.create_window((0, 0), window=self.grille, anchor="nw")
        self.grille.bind("<Configure>",
                         lambda _e: canvas.configure(scrollregion=canvas.bbox("all")))
        canvas.bind("<Configure>", lambda e: canvas.itemconfigure(win, width=e.width))
        # Molette limitée au survol : `bind_all` capterait celle des autres onglets.
        canvas.bind("<Enter>", lambda _e: canvas.bind_all(
            "<MouseWheel>", lambda e: canvas.yview_scroll(int(-e.delta / 120), "units")))
        canvas.bind("<Leave>", lambda _e: canvas.unbind_all("<MouseWheel>"))

        self._build_grid()
        self.refresh()

    # ------------------------------------------------------------------ #
    def _build_grid(self):
        for enfant in self.grille.winfo_children():
            enfant.destroy()
        self.vars.clear()
        cats = mime_catalog.categories()
        if not cats:
            ttk.Label(self.grille, foreground="#b91c1c", text=i18n.t(
                "picker.no_catalog",
                "Aucune catégorie connue : le référentiel de types n'est pas "
                "chargé (voir Maintenance → Types MIME).")).grid(
                    row=0, column=0, sticky="w", padx=6, pady=6)
            return
        for i in range(COLONNES):
            self.grille.columnconfigure(i, weight=1, uniform="cat")
        lignes = (len(cats) + COLONNES - 1) // COLONNES
        for index, (nom, libelle) in enumerate(cats):
            var = tk.BooleanVar(value=False)
            var.trace_add("write", lambda *_a: self._refresh_count())
            self.vars[nom] = var
            texte = libelle
            if nom == mime_catalog.CATEGORY_ROOT:
                texte += "  " + i18n.t("picker.root_hint", "(= tout, donc aucun filtre)")
            ttk.Checkbutton(self.grille, variable=var, text=texte).grid(
                row=index % lignes, column=index // lignes,
                sticky="w", padx=6, pady=1)

    def _set_all(self, valeur: bool):
        for var in self.vars.values():
            var.set(valeur)

    def _cochees(self) -> list[str]:
        return [nom for nom, var in self.vars.items() if var.get()]

    def _refresh_count(self):
        n = len(self._cochees())
        self.lbl_count.config(text=i18n.t(
            "picker.count", "{n} catégorie(s) cochée(s) sur {t}.",
            n=n, t=len(self.vars)))

    # ------------------------------------------------------------------ #
    def refresh(self):
        """Relit le filtre du profil courant et repositionne les cases.

        Un filtre qui n'est **pas** représentable ici (mode exclude, ou types
        nommés un par un) laisse les cases vides et le dit : on ne convertit
        pas, on ne devine pas — cf. l'avertissement en tête de module.
        """
        # Le référentiel peut avoir changé depuis la construction (import d'un
        # .properties, apprentissage) : on rebâtit la grille si le nombre de
        # catégories a bougé, sinon des cases manqueraient sans rien dire.
        if len(self.vars) != len(mime_catalog.categories()):
            self._build_grid()
        filtre = self._get_filter() or ""
        mode = (self._get_mode() or "").strip().lower()
        cochables = mode.startswith("include") \
            and mime_catalog.filter_is_only_categories(filtre)
        voulues = set(mime_catalog.filter_categories(filtre)) if cochables else set()
        for nom, var in self.vars.items():
            var.set(nom in voulues)
        self._refresh_count()

        if cochables:
            etat = i18n.t("picker.state_ok",
                          "Le filtre de ce profil est composé de catégories : les "
                          "cases ci-dessous le reflètent.")
            couleur = "#166534"
        elif not filtre.strip():
            etat = i18n.t("picker.state_empty",
                          "Ce profil n'a aucun filtre : tous les types sont indexés. "
                          "Cochez ce que vous voulez indexer, puis « Appliquer ».")
            couleur = "#475569"
        elif not mode.startswith("include"):
            etat = i18n.t(
                "picker.state_exclude",
                "Ce profil porte un filtre en mode « exclude » — il désigne ce qui "
                "est ÉCARTÉ. Il n'est pas converti ici : appliquer une sélection le "
                "remplacerait par un filtre « include ».")
            couleur = "#b45309"
        else:
            etat = i18n.t(
                "picker.state_types",
                "Ce profil filtre des types nommés un par un, pas des catégories. "
                "Appliquer une sélection remplacerait ce filtre.")
            couleur = "#b45309"
        self.lbl_state.config(text=etat, foreground=couleur)

    # ------------------------------------------------------------------ #
    def _apply(self):
        """Écrit la sélection dans le profil — toujours en mode ``include``."""
        titre = i18n.t("picker.title", "Catégories à indexer")
        cochees = self._cochees()
        ancien = (self._get_filter() or "").strip()

        if not cochees:
            # Zéro coche en include voudrait dire « n'indexer que rien ». On
            # traduit l'intention la plus probable — retirer le filtre — et on
            # le demande, parce que c'est une perte de réglage.
            if not ancien:
                messagebox.showinfo(titre, i18n.t(
                    "picker.nothing_to_do",
                    "Aucune catégorie cochée et aucun filtre existant : rien à faire."))
                return
            if not messagebox.askyesno(titre, i18n.t(
                    "picker.confirm_clear",
                    "Aucune catégorie n'est cochée. Retirer complètement le filtre "
                    "de ce profil (tous les types seront indexés) ?")):
                return
            self._set_filter("", "exclude")
            self.app.log.log(i18n.t("picker.cleared", "Filtre de types retiré du profil."))
            self.refresh()
            return

        if mime_catalog.CATEGORY_ROOT in cochees and len(cochees) > 1:
            messagebox.showinfo(titre, i18n.t(
                "picker.root_warning",
                "« Tout » est coché : les autres cases ne changent rien. Décochez-la "
                "pour restreindre l'indexation."))

        nouveau = mime_catalog.build_category_filter(cochees)
        if ancien and ancien != nouveau and not messagebox.askyesno(titre, i18n.t(
                "picker.confirm_replace",
                "Ce profil a déjà un filtre. Le remplacer par les {n} catégorie(s) "
                "cochée(s) ?", n=len(cochees))):
            return
        self._set_filter(nouveau, "include")
        self.app.log.log(i18n.t(
            "picker.applied",
            "Filtre du profil : {n} catégorie(s), mode include.", n=len(cochees)))
        self.refresh()
