"""Sous-onglet **Types de fichiers à indexer** : composer le filtre du profil.

**Pourquoi ce module existe (11/09/2026).** Quatre endroits parlaient des types
MIME et se contredisaient : le champ « Filtre » du formulaire Réglages, un popup
« Voir les types » à deux panneaux, un sélecteur de catégories à cases à cocher,
et un sous-onglet « Référentiel ». Ajouter un type dans le popup ne cochait rien
dans le sélecteur — deux mécanismes qui ne se parlaient pas — et le sélecteur
annonçait « ce ne sont pas des catégories » juste au-dessus de « 4 catégorie(s)
cochée(s) sur 78 ». Constat de l'utilisateur : *« trop de panneaux qui font au
final doublon »*.

Tout est réuni ici, et **les cases à cocher disparaissent** : on compose le
filtre en **ajoutant** des entrées prises dans le référentiel, à droite (bouton
ou double-clic), et on les retire à gauche du même geste.

⚠ **On ne décrit PAS un type ici** (11/09/2026). Le bouton « Décrire ce type… »
y a vécu une journée : nommer un type est un geste de **référentiel**, pas de
profil, et il existe déjà — au même endroit que le reste de l'entretien,
Maintenance → Types MIME. Deux points d'entrée pour la même chose, c'était
reprendre le défaut que ce module vient de corriger.

⚠ **Le classement de droite groupe par FAMILLE MIME** (``application/``,
``image/``, ``category/``…), pas par catégorie Intella. Ce n'est pas un choix
d'ergonomie mais une contrainte des données : le fichier de descriptions de
Vound liste ``category/documents=Documents`` **et** ``application/pdf=Adobe
PDF`` sans jamais dire que le second appartient au premier. La famille est la
seule appartenance réellement présente dans les noms.

⚠ **Le mode du filtre est en tête, et c'est sa PHRASE qui porte la couleur** :
rouge pour « exclude » (ces types sont écartés, tout le reste est indexé), vert
pour « include » (seuls ceux-là sont indexés). Le défaut est ``exclude`` : une
liste composée comme « ce que je veux » ferait alors exactement l'inverse, et
Intella ne permet pas de revoir les réglages d'une source après l'import.
"""

import tkinter as tk
from tkinter import ttk

import config
import i18n
import mime_catalog
import ui_theme
from ui_widgets import (MIME_STATUS_COLORS, attach_tip, make_button,
                        mime_filter_sense, mime_status_label)

# Clés du groupe « Filtres » du catalogue, construites ici plutôt que dans le
# formulaire Réglages : elles parlent toutes du même sujet que ce panneau.
CLE_FILTRE = "sourceTypeFilter"
CLE_MODE = "sourceTypeFilterMode"
CLES_ANNEXES = ("sourceHashFilters", "fileNameFilters")

# Familles connues, dans l'ordre d'affichage. Les catégories d'Intella d'abord :
# c'est ce qu'on met le plus souvent dans un filtre (78 entrées, toutes décrites,
# contre ~600 types dont 121 sans libellé).
_ORDRE_FAMILLES = ["category", "application", "message", "text", "image",
                   "audio", "video", "multipart", "model", "font"]


def famille(nom: str) -> str:
    """Famille MIME d'un type (``application/pdf`` → ``application``)."""
    nom = (nom or "").strip()
    if not nom:
        return ""
    return nom.split("/", 1)[0] if "/" in nom else nom


def _rang_famille(f: str) -> tuple:
    return (_ORDRE_FAMILLES.index(f), "") if f in _ORDRE_FAMILLES else (99, f)


class TypesPanel(ttk.Frame):
    """Les deux panneaux du filtre + les filtres annexes.

    ``owner`` est le ``ProfilesTab`` : ce panneau y **enregistre ses widgets**
    (``vars`` / ``_text_widgets``) pour que ``_collect_values`` et
    ``_load_values`` continuent de fonctionner sans savoir où vivent les champs.
    """

    def __init__(self, parent, app, owner):
        super().__init__(parent)
        self.app = app
        self.owner = owner
        self._cat_seules = tk.BooleanVar(value=True)
        self._recherche = tk.StringVar()
        self._filtre_courant = []          # noms, dans l'ordre de saisie
        # 🐞 Cette variable est la LIAISON avec le profil. Sans elle, la clé
        # `sourceTypeFilter` n'existait nulle part une fois le groupe « Filtres »
        # sorti du formulaire Réglages : `_collect_values` ne la trouvait pas et
        # **un profil enregistré perdait silencieusement son filtre de types**.
        self.var_filtre = tk.StringVar()
        self.owner.vars[CLE_FILTRE] = self.var_filtre

        # Les boutons se grisent, mais le double-clic, lui, ne se grise pas :
        # sans ce drapeau on pourrait composer un filtre sur « Défaut Intella »
        # (lecture seule) et le perdre à la sélection suivante.
        self._editable = True
        self._boutons = []
        pad, gap = app.theme.pad, app.theme.gap
        self._build_mode(pad, gap)
        self._build_panneaux(pad, gap)
        self._build_annexes(pad, gap)
        self.refresh_catalogue()

    # ------------------------------------------------------------------ #
    # En-tête : le mode, et ce qu'il fait                                #
    # ------------------------------------------------------------------ #
    def _build_mode(self, pad, gap):
        barre = ttk.Frame(self)
        barre.pack(fill="x", padx=pad, pady=(gap, 0))

        # Le LIBELLÉ est neutre ; c'est la PHRASE de droite qui porte la couleur
        # (11/09/2026). Un intitulé rouge en permanence criait au danger même
        # quand le filtre était inoffensif, et ne disait rien du mode courant.
        lbl = ttk.Label(barre, text=i18n.t("profiles.filter_mode_label",
                                           "Mode du filtre de types"),
                        foreground=config.UI_INK, font=ui_theme.F_BOLD)
        lbl.pack(side="left")
        attach_tip(lbl, i18n.t(
            "profiles.filter_mode_tip",
            "« exclude » : les types listés sont ÉCARTÉS, tout le reste est indexé.\n"
            "« include » : SEULS les types listés sont indexés.\n\n"
            "C'est « exclude » par défaut, comme dans Intella : une liste composée "
            "comme « ce que je veux garder » ferait alors exactement l'inverse."))

        self.var_mode = tk.StringVar(value="exclude")
        cb = ttk.Combobox(barre, textvariable=self.var_mode, width=12,
                          values=["exclude", "include"])
        cb.pack(side="left", padx=8)
        self.owner.vars[CLE_MODE] = self.var_mode
        self.owner._widgets[CLE_MODE] = cb
        self.var_mode.trace_add("write", lambda *_a: self._refresh_sens())

        self.lbl_sens = ttk.Label(barre, font=ui_theme.F_BOLD)
        self.lbl_sens.pack(side="left", padx=4)
        self._refresh_sens()

    def _refresh_sens(self):
        """La phrase dit ce que la liste FAIT — et sa couleur le redit.

        Rouge en « exclude » (ces types partent à la poubelle, tout le reste est
        indexé), vert en « include » (seuls ceux-là sont indexés) — le vert de
        « Enregistrer », pour que l'œil rapproche les deux.
        """
        inclus = (self.var_mode.get() or "").strip().lower().startswith("include")
        self.lbl_sens.configure(
            text=mime_filter_sense(self.var_mode.get()),
            foreground=config.ACTION_COLOR if inclus else config.DANGER_COLOR)

    # ------------------------------------------------------------------ #
    # Les deux panneaux                                                   #
    # ------------------------------------------------------------------ #
    def _build_panneaux(self, pad, gap):
        split = ttk.PanedWindow(self, orient="horizontal")
        split.pack(fill="both", expand=True, padx=pad, pady=gap)

        # --- Gauche : ce que le filtre contient --------------------------- #
        gauche = ttk.LabelFrame(split, text=i18n.t("mime.pane_current",
                                                   "Types inclus dans ce filtre"))
        split.add(gauche, weight=1)
        # ⚠ Le pied se place AVANT le tableau. `_table` empile son Treeview avec
        # `side="left"` et `expand=True` : un pied ajouté après se retrouverait
        # PAR-DESSUS la liste (constaté à la première capture v3.1).
        pied = ttk.Frame(gauche)
        pied.pack(side="bottom", fill="x", padx=6, pady=(0, 6))
        self.lbl_compte = ttk.Label(pied, style="Hint.TLabel")
        self.lbl_compte.pack(side="left")
        self._ajoute_bouton(
            make_button(pied, i18n.t("mime.remove_all", "Tout retirer"),
                        self._retirer_tout, outline=config.DANGER_COLOR)
        ).pack(side="right")
        self._ajoute_bouton(
            make_button(pied, i18n.t("mime.remove", "Retirer du filtre"), self._retirer)
        ).pack(side="right", padx=4)

        self.tree_filtre = self._table(gauche, ("name", "label", "state"), (
            (i18n.t("mime.col_name", "Type"), 240),
            (i18n.t("mime.col_label", "Description"), 190),
            (i18n.t("mime.col_state", "État"), 120)))
        # Les quatre états ne s'expliquent pas d'eux-mêmes : sans cette bulle,
        # « inconnu » se lit comme une erreur alors que c'est le plus souvent un
        # alias qu'Intella écrit sans le nommer.
        attach_tip(self.tree_filtre, i18n.t(
            "mime.states_tip",
            "État d'un type dans le référentiel :\n"
            "• décrit — libellé fourni par Vound ;\n"
            "• décrit par vous — libellé que vous avez saisi ;\n"
            "• connu, sans libellé — le nom existe (Intella l'écrit), mais "
            "personne ne le décrit. C'est un synonyme valide, il n'y a rien à "
            "corriger ;\n"
            "• inconnu — jamais rencontré. Vérifiez l'orthographe, ou votre "
            "version d'Intella est plus récente que le référentiel."))
        # Double-clic = retirer. Le geste inverse de celui du référentiel, à
        # droite, où il ajoute (demande du 11/09/2026).
        self.tree_filtre.bind("<Double-1>", lambda _e: self._retirer())

        # --- Droite : le référentiel, et l'édition des descriptions ------- #
        droite = ttk.LabelFrame(split, text=i18n.t(
            "mime.pane_catalog", "Types disponibles (référentiel)"))
        split.add(droite, weight=1)

        barre = ttk.Frame(droite)
        barre.pack(fill="x", padx=6, pady=(6, 2))
        ttk.Label(barre, text=i18n.t("mime.search", "Rechercher")).pack(side="left")
        e = ttk.Entry(barre, textvariable=self._recherche)
        e.pack(side="left", fill="x", expand=True, padx=6)
        e.bind("<KeyRelease>", lambda _e: self.refresh_catalogue())
        chk = ttk.Checkbutton(barre, variable=self._cat_seules,
                              command=self.refresh_catalogue,
                              text=i18n.t("mime.only_categories", "Catégories seules"))
        chk.pack(side="left")
        attach_tip(chk, i18n.t(
            "mime.only_categories_tip",
            "Coché : seules les 78 catégories d'Intella, toutes décrites — c'est "
            "ce qu'on met le plus souvent dans un filtre.\n"
            "Décoché : tous les types, rangés par famille (application, image, "
            "text…). La famille est la seule appartenance que le référentiel de "
            "Vound permette de déduire ; il n'indique pas à quelle catégorie "
            "d'Intella appartient un type."))

        # ⚠ Le pied AVANT le tableau, comme à gauche : `pack(side="left",
        # expand=True)` du Treeview prend sinon toute la place et refoule le
        # pied dans le coin bas-droit — c'est ce qui plaçait « ◀ Ajouter au
        # filtre » à l'opposé du panneau qu'il alimente, et tronquait le
        # compteur en « 33 t ».
        pied = ttk.Frame(droite)
        pied.pack(side="bottom", fill="x", padx=6, pady=(0, 6))
        self._ajoute_bouton(
            make_button(pied, i18n.t("mime.add_to_filter", "◀ Ajouter au filtre"),
                        self._ajouter, color=config.ACTION_COLOR)
        ).pack(side="left")
        self.lbl_ref = ttk.Label(pied, style="Hint.TLabel")
        self.lbl_ref.pack(side="left", padx=8)

        self.tree_cat = ttk.Treeview(droite, columns=("label", "state"),
                                     show="tree headings", selectmode="extended")
        self.tree_cat.heading("#0", text=i18n.t("mime.col_name", "Type"))
        self.tree_cat.heading("label", text=i18n.t("mime.col_label", "Description"))
        self.tree_cat.heading("state", text=i18n.t("mime.col_state", "État"))
        self.tree_cat.column("#0", width=300, stretch=True)
        self.tree_cat.column("label", width=200, anchor="w")
        self.tree_cat.column("state", width=120, anchor="w")
        vsb = ttk.Scrollbar(droite, orient="vertical", command=self.tree_cat.yview)
        self.tree_cat.configure(yscrollcommand=vsb.set)
        self.tree_cat.pack(side="left", fill="both", expand=True, padx=(6, 0), pady=2)
        vsb.pack(side="right", fill="y", pady=2)
        for etat, couleur in MIME_STATUS_COLORS.items():
            self.tree_cat.tag_configure(etat, foreground=couleur)
        self.tree_cat.tag_configure("famille", font=ui_theme.F_BOLD)
        self.tree_cat.bind("<Double-1>", self._double_clic_catalogue)
        attach_tip(self.tree_cat, i18n.t(
            "mime.catalog_tip",
            "Double-cliquez un type pour l'ajouter au filtre, à gauche "
            "(sélection multiple possible, puis « ◀ Ajouter au filtre »).\n"
            "Un double-clic sur une famille l'ouvre ou la referme.\n\n"
            "Pour donner un libellé à un type, passez par Maintenance → "
            "Types MIME."))

    def _ajoute_bouton(self, bouton):
        """Enregistre un bouton pour que `set_editable` puisse le griser.

        Ses couleurs d'origine sont mémorisées sur le widget : `set_editable`
        doit pouvoir les rendre, et Tk ne garde aucune trace de ce qu'elles
        étaient avant le grisage.
        """
        bouton._bg_actif = bouton.cget("bg")
        bouton._fg_actif = bouton.cget("fg")
        bouton._bord_actif = bouton.cget("highlightbackground")
        self._boutons.append(bouton)
        return bouton

    @staticmethod
    def _table(parent, colonnes, entetes):
        tree = ttk.Treeview(parent, columns=colonnes, show="headings",
                            selectmode="extended")
        for col, (titre, largeur) in zip(colonnes, entetes, strict=True):
            tree.heading(col, text=titre)
            tree.column(col, width=largeur, anchor="w")
        vsb = ttk.Scrollbar(parent, orient="vertical", command=tree.yview)
        tree.configure(yscrollcommand=vsb.set)
        tree.pack(side="left", fill="both", expand=True, padx=(6, 0), pady=6)
        vsb.pack(side="right", fill="y", pady=6)
        for etat, couleur in MIME_STATUS_COLORS.items():
            tree.tag_configure(etat, foreground=couleur)
        return tree

    # ------------------------------------------------------------------ #
    # Filtres annexes (hachages, noms de fichiers)                       #
    # ------------------------------------------------------------------ #
    def _build_annexes(self, pad, gap):
        box = ttk.LabelFrame(self, text=i18n.t("profiles.other_filters",
                                               "Autres filtres"))
        box.pack(fill="x", padx=pad, pady=(0, gap))
        box.columnconfigure(1, weight=1)
        import profile_catalog
        catalogue = {o["key"]: o for _g, opts in profile_catalog.GROUPS for o in opts}
        for ligne, cle in enumerate(CLES_ANNEXES):
            o = catalogue.get(cle)
            if not o:
                continue
            libelle = i18n.t(o["label_key"], o["label"])
            lbl = ttk.Label(box, text=libelle)
            lbl.grid(row=ligne, column=0, sticky="w", padx=6, pady=3)
            var = tk.StringVar(value=str(o["default"]))
            champ = ttk.Entry(box, textvariable=var)
            champ.grid(row=ligne, column=1, sticky="ew", padx=6, pady=3)
            self.owner.vars[cle] = var
            self.owner._widgets[cle] = champ
            if cle == "fileNameFilters":
                attach_tip(champ, i18n.t(
                    "profiles.filename_filter_tip",
                    "Jokers autorisés dans les noms de fichiers : "
                    "« ? » (un caractère) et « * » (plusieurs). "
                    "Ex. : rapport_*.pdf, IMG_????.jpg"))
            else:
                attach_tip(champ, i18n.t(
                    "profiles.hash_filter_tip",
                    "Chemins de fichiers .md5, séparés par des virgules. Les items "
                    "dont l'empreinte y figure sont écartés de l'indexation.\n"
                    "⚠ Le chemin doit être visible DEPUIS LE SERVEUR Intella, pas "
                    "depuis ce poste."))

    # ------------------------------------------------------------------ #
    # Contenu                                                            #
    # ------------------------------------------------------------------ #
    def set_filter_text(self, texte: str):
        """Charge le filtre du profil (appelé par ``ProfilesTab``)."""
        self._filtre_courant = mime_catalog.split_filter(texte or "")
        self._refresh_filtre()

    def get_filter_text(self) -> str:
        return ",".join(self._filtre_courant)

    def _refresh_filtre(self):
        self.tree_filtre.delete(*self.tree_filtre.get_children())
        for i, nom in enumerate(self._filtre_courant):
            etat = mime_catalog.status(nom)
            affiche = nom or i18n.t("mime.untyped", "(sans type)")
            self.tree_filtre.insert(
                "", "end", iid=str(i),
                values=(affiche, mime_catalog.label(nom) or "",
                        mime_status_label(etat)), tags=(etat,))
        self.lbl_compte.configure(text=i18n.t(
            "mime.count_in_filter", "{n} type(s) dans ce filtre",
            n=len(self._filtre_courant)))
        self._notifier()

    def _notifier(self):
        """Répercute la liste dans la variable que le profil enregistre."""
        self.var_filtre.set(self.get_filter_text())

    def refresh_catalogue(self):
        """Remplit le référentiel : à plat si « catégories seules », sinon par famille."""
        self.tree_cat.delete(*self.tree_cat.get_children())
        motif = self._recherche.get().strip().lower()
        if self._cat_seules.get():
            entrees = [(nom, lib) for nom, lib in mime_catalog.categories()]
            entrees = [(n, l) for n, l in entrees
                       if not motif or motif in n.lower() or motif in (l or "").lower()]
            for nom, lib in entrees:
                etat = mime_catalog.status(nom)
                self.tree_cat.insert("", "end", text=nom,
                                     values=(lib or "", mime_status_label(etat)),
                                     tags=(etat,))
            self.lbl_ref.configure(text=i18n.t("mime.ref_categories",
                                               "{n} catégorie(s)", n=len(entrees)))
            return

        trouves = mime_catalog.search(motif, limit=5000)
        groupes = {}
        for nom, etat, _describe in trouves:
            # cf. `ui_maintenance` : `label()`, pas `describe()` — sinon un type
            # sans libellé s'affiche avec son propre nom en guise de description.
            groupes.setdefault(famille(nom), []).append(
                (nom, etat, mime_catalog.label(nom) or ""))
        total = 0
        for f in sorted(groupes, key=_rang_famille):
            noeud = self.tree_cat.insert(
                "", "end", text=f or i18n.t("mime.family_other", "(autres)"),
                values=(i18n.t("mime.family_count", "{n} type(s)",
                               n=len(groupes[f])), ""),
                open=bool(motif), tags=("famille",))
            for nom, etat, libelle in sorted(groupes[f]):
                total += 1
                self.tree_cat.insert(
                    noeud, "end", text=nom or i18n.t("mime.untyped", "(sans type)"),
                    values=(libelle or "", mime_status_label(etat)), tags=(etat,))
        self.lbl_ref.configure(text=i18n.t(
            "mime.ref_types", "{n} type(s) dans {f} famille(s)",
            n=total, f=len(groupes)))

    def set_editable(self, editable: bool):
        """Grise ce qui modifie le filtre (profil « Défaut Intella »).

        Le formulaire Réglages est grisé par `_set_form_state` via ses widgets ;
        ce panneau n'en enregistre pas pour ses boutons, il doit donc suivre
        lui-même — sinon on pourrait composer un filtre sur un profil en
        lecture seule, et le perdre à la sélection suivante.
        """
        self._editable = bool(editable)
        etat = "normal" if editable else "disabled"
        for bouton in self._boutons:
            try:
                # `state="disabled"` seul ne change que la couleur du TEXTE : un
                # bouton plein (l'action verte) reste vert vif et paraît actif.
                # On lui rend aussi son fond neutre.
                if editable:
                    bouton.configure(state=etat, bg=bouton._bg_actif,
                                     fg=bouton._fg_actif,
                                     highlightbackground=bouton._bord_actif)
                else:
                    bouton.configure(state=etat, bg=config.UI_SURFACE_2,
                                     fg=config.UI_INK_3,
                                     highlightbackground=config.UI_LINE)
            except tk.TclError:
                pass

    # ------------------------------------------------------------------ #
    # Actions                                                            #
    # ------------------------------------------------------------------ #
    def _noms_selectionnes(self) -> list:
        """Noms cochés à droite. Un nœud de famille rend tous ses enfants."""
        noms = []
        for iid in self.tree_cat.selection():
            enfants = self.tree_cat.get_children(iid)
            if enfants:                       # nœud de famille
                noms.extend(self.tree_cat.item(e, "text") for e in enfants)
            else:
                noms.append(self.tree_cat.item(iid, "text"))
        # Le type « Untyped » a pour nom la chaîne VIDE : son libellé d'affichage
        # doit redevenir vide, sinon on écrirait « (sans type) » dans le filtre.
        vide = i18n.t("mime.untyped", "(sans type)")
        return ["" if n == vide else n for n in noms]

    def _double_clic_catalogue(self, event):
        """Ajoute au filtre — sauf sur un nœud de famille, qui s'ouvre.

        Ajouter d'un coup les 400 types d'``application/`` parce qu'on a
        double-cliqué sur le pli serait une surprise coûteuse : le filtre n'est
        pas revérifiable après l'import.
        """
        iid = self.tree_cat.identify_row(event.y)
        if not iid or self.tree_cat.get_children(iid):
            return None                      # famille : laisser jouer le pli
        self.tree_cat.selection_set(iid)
        self._ajouter()
        return "break"

    def _ajouter(self):
        if not self._editable:
            return
        ajoutes = 0
        for nom in self._noms_selectionnes():
            if nom not in self._filtre_courant:
                self._filtre_courant.append(nom)
                ajoutes += 1
        if ajoutes:
            self._refresh_filtre()
            self.app.log.log(i18n.t("mime.added_log",
                                    "{n} type(s) ajouté(s) au filtre du profil.",
                                    n=ajoutes))

    def _retirer(self):
        if not self._editable:
            return
        indices = sorted((int(i) for i in self.tree_filtre.selection()), reverse=True)
        for i in indices:
            del self._filtre_courant[i]
        if indices:
            self._refresh_filtre()

    def _retirer_tout(self):
        if not self._editable or not self._filtre_courant:
            return
        self._filtre_courant = []
        self._refresh_filtre()
