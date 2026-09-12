"""Apparence commune de l'application : polices, couleurs, styles ttk, densité.

**Pourquoi un module dédié.** Jusqu'à la v2.9d, chaque onglet posait ses propres
polices et ses propres couleurs au fil de sa construction : changer la densité
d'affichage aurait demandé de retoucher six fichiers, et deux panneaux voisins
finissaient par ne pas s'aligner. Tout ce qui relève de l'apparence passe
désormais par ici.

**Densité à chaud (décision D9, 11/09/2026).** Le poste de labo va du portable
13 pouces au 22 pouces : la même fenêtre doit pouvoir se resserrer ou respirer.
La bascule se fait **sans redémarrer**, ce qui n'est possible qu'à deux
conditions, toutes deux tenues ici :

- les polices sont des **objets Tk nommés** (``tkinter.font.Font(name=…)``) —
  redimensionner l'objet met à jour tous les widgets qui s'y réfèrent, alors
  qu'un tuple ``("Segoe UI", 9)`` est copié à la création et fige le widget ;
- les ``tk.Button`` (dont le fond n'est pas stylable en ttk sous Windows, cf.
  ``ui_widgets.make_button``) sont **enregistrés** à leur création dans un
  ``WeakSet``, et leur rembourrage est recalculé à chaque bascule.

Le thème ttk est **clam** : sous « vista », le fond d'un en-tête de Treeview,
d'un Frame ttk ou d'un Notebook n'est pas modifiable, et l'application ne
pourrait pas avoir d'apparence propre.
"""

import tkinter as tk
import tkinter.font as tkfont
import weakref
from tkinter import ttk

import config

# --- Densités d'affichage -------------------------------------------------- #
# `base` = corps de la police de texte ; le reste en découle. `row` est la
# hauteur d'une ligne de Treeview : c'est elle qui décide du nombre de sources
# visibles sans défiler, donc le réglage qui compte vraiment sur un portable.
COMPACT = "compacte"
NORMAL = "normale"
COMFORT = "confortable"
DENSITIES = (COMPACT, NORMAL, COMFORT)

_DENSITY = {
    COMPACT: {"base": 9, "row": 20, "padx": 8, "pady": 2, "gap": 4, "cell": 3},
    NORMAL: {"base": 9, "row": 23, "padx": 10, "pady": 4, "gap": 6, "cell": 5},
    COMFORT: {"base": 10, "row": 28, "padx": 13, "pady": 6, "gap": 9, "cell": 7},
}

# Échelle de la police, en pourcent (bouton A− / A+ de Maintenance → Options).
SCALE_MIN, SCALE_MAX, SCALE_STEP = 80, 140, 10

_FAMILY = "Segoe UI"
_MONO = "Consolas"

# Noms des objets Font partagés (cf. docstring : nommés = redimensionnables).
F_BODY = "IFBody"
F_BOLD = "IFBold"
F_SMALL = "IFSmall"
F_MONO = "IFMono"
F_TITLE = "IFTitle"
F_STEP = "IFStep"
F_BTN = "IFButton"
# Barrée : une source déjà présente dans le cas reste lisible mais montre
# qu'elle ne partira pas à l'import (décision D7).
F_STRIKE = "IFStrike"


# Instance courante. `ui_widgets.make_button` s'y réfère pour enregistrer chaque
# bouton tk sans que les ~60 appels existants aient à transporter l'application.
_ACTIVE = None


def current():
    """Thème actif, ou ``None`` hors application (tests, import isolé)."""
    return _ACTIVE


class Theme:
    """État d'apparence d'une fenêtre : polices nommées, styles ttk, métriques.

    Une seule instance par application, publiée en ``app.theme``. Les modules
    d'interface lisent ``theme.pad``/``theme.gap`` plutôt que des nombres en dur
    pour que la densité les atteigne.
    """

    def __init__(self, root: tk.Tk, density: str = NORMAL, scale: int = 100):
        global _ACTIVE
        _ACTIVE = self
        self.root = root
        self.density = density if density in DENSITIES else NORMAL
        self.scale = _clamp_scale(scale)
        # Boutons tk suivis pour leur rendre le rembourrage à chaque bascule.
        self._buttons = weakref.WeakSet()
        self._style = ttk.Style(root)
        try:
            self._style.theme_use("clam")
        except tk.TclError:          # thème absent : on garde celui en place
            pass
        self._make_fonts()
        self.apply()

    # ------------------------------------------------------------------ #
    # Polices                                                            #
    # ------------------------------------------------------------------ #
    def _make_fonts(self):
        """Crée (une fois) les objets Font nommés, partagés par tous les widgets.

        🐞 **Les objets doivent être GARDÉS en référence.** Un
        ``tkinter.font.Font`` créé (donc ``exists=False``) porte
        ``delete_font=True`` : quand le ramasse-miettes de Python le libère, son
        ``__del__`` exécute ``font delete`` et la police nommée **disparaît côté
        Tcl**. Une boucle qui les crée sans les stocker laisse donc un Tk sans
        aucune de ses polices — symptôme exact au premier lancement de la v3.0 :
        « named font IFBody does not already exist », levé par le tout premier
        ``apply()``. Même piège que les images ``PhotoImage``.
        """
        self._fonts = {}
        for name, family in ((F_BODY, _FAMILY), (F_BOLD, _FAMILY), (F_SMALL, _FAMILY),
                             (F_TITLE, _FAMILY), (F_STEP, _FAMILY), (F_BTN, _FAMILY),
                             (F_STRIKE, _FAMILY), (F_MONO, _MONO)):
            try:
                f = tkfont.Font(root=self.root, name=name, family=family,
                                size=9, exists=True)
            except tk.TclError:
                f = tkfont.Font(root=self.root, name=name, family=family, size=9)
            self._fonts[name] = f

    def font(self, name: str) -> tkfont.Font:
        return self._fonts[name]

    def _size(self, delta: int = 0) -> int:
        """Corps de police pour la densité et l'échelle courantes."""
        base = _DENSITY[self.density]["base"] + delta
        return max(7, round(base * self.scale / 100))

    # ------------------------------------------------------------------ #
    # Application                                                        #
    # ------------------------------------------------------------------ #
    def set_density(self, density: str) -> None:
        if density in DENSITIES and density != self.density:
            self.density = density
            self.apply()

    def set_scale(self, scale: int) -> None:
        scale = _clamp_scale(scale)
        if scale != self.scale:
            self.scale = scale
            self.apply()

    @property
    def metrics(self) -> dict:
        return _DENSITY[self.density]

    @property
    def pad(self) -> int:
        """Rembourrage extérieur d'un panneau (marges de page)."""
        return self.metrics["padx"]

    @property
    def gap(self) -> int:
        """Espace entre deux éléments voisins."""
        return self.metrics["gap"]

    @property
    def row_height(self) -> int:
        return max(16, round(self.metrics["row"] * self.scale / 100))

    def apply(self) -> None:
        """Recalcule polices, styles ttk et boutons tk. Appelable à chaud."""
        n = self._size()
        self.font(F_BODY).configure(size=n, weight="normal")
        self.font(F_BOLD).configure(size=n, weight="bold")
        self.font(F_SMALL).configure(size=max(7, n - 1), weight="normal")
        self.font(F_MONO).configure(size=max(7, n - 1), weight="normal")
        self.font(F_TITLE).configure(size=n + 2, weight="bold")
        self.font(F_STEP).configure(size=n + 1, weight="bold")
        self.font(F_BTN).configure(size=n, weight="bold")
        self.font(F_STRIKE).configure(size=n, weight="normal", overstrike=True)
        self._apply_styles()
        self._apply_buttons()

    def _apply_styles(self):
        s = self._style
        m = self.metrics
        cell = m["cell"]

        self.root.configure(background=config.UI_BG)
        s.configure(".", background=config.UI_BG, foreground=config.UI_INK,
                    font=F_BODY, borderwidth=0, focuscolor=config.ACCENT)

        s.configure("TFrame", background=config.UI_BG)
        s.configure("Surface.TFrame", background=config.UI_SURFACE)
        s.configure("Line.TFrame", background=config.UI_LINE)
        s.configure("Soft.TFrame", background=config.UI_SURFACE_2)
        s.configure("Accent.TFrame", background=config.ACCENT_SOFT)

        s.configure("TLabel", background=config.UI_BG, foreground=config.UI_INK, font=F_BODY)
        s.configure("Surface.TLabel", background=config.UI_SURFACE)
        s.configure("Soft.TLabel", background=config.UI_SURFACE_2, foreground=config.UI_INK_2)
        s.configure("Hint.TLabel", background=config.UI_BG,
                    foreground=config.UI_INK_3, font=F_SMALL)
        s.configure("HintSurface.TLabel", background=config.UI_SURFACE,
                    foreground=config.UI_INK_3, font=F_SMALL)
        s.configure("Title.TLabel", background=config.UI_SURFACE,
                    foreground=config.UI_INK, font=F_TITLE)
        s.configure("Section.TLabel", background=config.UI_SURFACE,
                    foreground=config.UI_INK_3, font=F_SMALL)
        s.configure("Warn.TLabel", background=config.UI_BG, foreground=config.WARN_COLOR)
        s.configure("Danger.TLabel", background=config.UI_BG, foreground=config.DANGER_COLOR)
        s.configure("Go.TLabel", background=config.UI_BG, foreground=config.ACTION_COLOR)

        s.configure("TLabelframe", background=config.UI_BG, bordercolor=config.UI_LINE,
                    relief="solid", borderwidth=1)
        s.configure("TLabelframe.Label", background=config.UI_BG,
                    foreground=config.UI_INK_2, font=F_BOLD)

        s.configure("TEntry", fieldbackground=config.UI_SURFACE,
                    background=config.UI_SURFACE, foreground=config.UI_INK,
                    bordercolor=config.UI_LINE, lightcolor=config.UI_LINE,
                    darkcolor=config.UI_LINE, insertcolor=config.UI_INK,
                    padding=(cell + 1, cell))
        s.map("TEntry",
              bordercolor=[("focus", config.ACCENT)],
              lightcolor=[("focus", config.ACCENT)],
              fieldbackground=[("readonly", config.UI_SURFACE_2),
                               ("disabled", config.UI_SURFACE_2)],
              foreground=[("readonly", config.UI_INK_2),
                          ("disabled", config.UI_INK_3)])

        s.configure("TCombobox", fieldbackground=config.UI_SURFACE,
                    background=config.UI_SURFACE, foreground=config.UI_INK,
                    bordercolor=config.UI_LINE, lightcolor=config.UI_LINE,
                    darkcolor=config.UI_LINE, arrowcolor=config.UI_INK_2,
                    padding=(cell + 1, cell))
        # ⚠ Un Combobox `readonly` affiche son texte comme une SÉLECTION : sans
        # `selectforeground`/`selectbackground`, le thème clam peut le peindre
        # blanc sur blanc — le champ paraît alors VIDE alors qu'il a bien sa
        # valeur (symptôme rapporté sur « Langue », 11/09/2026).
        s.configure("TCombobox", selectbackground=config.UI_SURFACE,
                    selectforeground=config.UI_INK)
        s.map("TCombobox",
              bordercolor=[("focus", config.ACCENT)],
              fieldbackground=[("readonly", config.UI_SURFACE)],
              selectbackground=[("readonly", config.UI_SURFACE)],
              selectforeground=[("readonly", config.UI_INK)],
              foreground=[("readonly", config.UI_INK),
                          ("disabled", config.UI_INK_3)])

        s.configure("TCheckbutton", background=config.UI_BG, foreground=config.UI_INK,
                    focuscolor=config.ACCENT)
        s.map("TCheckbutton", background=[("active", config.UI_BG)])
        s.configure("Surface.TCheckbutton", background=config.UI_SURFACE)
        s.map("Surface.TCheckbutton", background=[("active", config.UI_SURFACE)])

        s.configure("TSeparator", background=config.UI_LINE)
        s.configure("TScrollbar", background=config.UI_SURFACE_2,
                    troughcolor=config.UI_BG, bordercolor=config.UI_BG,
                    arrowcolor=config.UI_INK_2)

        s.configure("TSpinbox", fieldbackground=config.UI_SURFACE,
                    bordercolor=config.UI_LINE, arrowcolor=config.UI_INK_2,
                    padding=(cell, cell - 1 if cell else 0))

        s.configure("Treeview", background=config.UI_SURFACE,
                    fieldbackground=config.UI_SURFACE, foreground=config.UI_INK,
                    rowheight=self.row_height, borderwidth=0, font=F_BODY)
        s.map("Treeview",
              background=[("selected", config.UI_SEL)],
              foreground=[("selected", config.UI_INK)])
        s.configure("Treeview.Heading", background=config.UI_HEAD,
                    foreground=config.UI_INK_2, font=F_SMALL, relief="flat",
                    padding=(cell + 2, cell))
        s.map("Treeview.Heading",
              background=[("active", config.ACCENT_SOFT)],
              foreground=[("active", config.ACCENT)])

        s.configure("TProgressbar", background=config.ACCENT,
                    troughcolor=config.UI_SURFACE, bordercolor=config.UI_LINE,
                    lightcolor=config.ACCENT, darkcolor=config.ACCENT)

        # Sous-onglets (Profils, Maintenance) : plats, soulignés quand actifs.
        s.configure("Sub.TNotebook", background=config.UI_BG, borderwidth=0,
                    tabmargins=(0, 0, 0, 0))
        s.configure("Sub.TNotebook.Tab", background=config.UI_BG,
                    foreground=config.UI_INK_2, font=F_BODY,
                    padding=(m["padx"] + 4, m["pady"] + 3), borderwidth=0)
        s.map("Sub.TNotebook.Tab",
              background=[("selected", config.UI_SURFACE)],
              foreground=[("selected", config.ACCENT)],
              font=[("selected", F_BOLD)])

        # Notebook principal : barre d'onglets SUPPRIMÉE (la navigation est
        # dessinée par `ui_nav`). On garde le Notebook pour ne pas réécrire la
        # gestion des pages, `aller_a` et le grisage d'un cas compound.
        try:
            s.layout("Headless.TNotebook.Tab", [])
        except tk.TclError:
            pass
        s.configure("Headless.TNotebook", background=config.UI_BG, borderwidth=0,
                    tabmargins=(0, 0, 0, 0))

    # ------------------------------------------------------------------ #
    # Boutons tk (fond colorable, donc hors ttk : cf. ui_widgets)        #
    # ------------------------------------------------------------------ #
    def register_button(self, widget: tk.Widget) -> None:
        self._buttons.add(widget)
        self._pad_button(widget)

    def _apply_buttons(self):
        for b in list(self._buttons):
            try:
                self._pad_button(b)
            except tk.TclError:      # widget détruit entre-temps
                pass

    def _pad_button(self, widget):
        m = self.metrics
        widget.configure(padx=m["padx"], pady=m["pady"] + 1)


def _clamp_scale(scale) -> int:
    try:
        scale = int(scale)
    except (TypeError, ValueError):
        return 100
    return max(SCALE_MIN, min(SCALE_MAX, scale))


def density_label(density: str) -> str:
    """Libellé traduit d'une densité (import tardif : i18n importe config)."""
    import i18n
    return {
        COMPACT: i18n.t("options.density_compact", "Compacte"),
        NORMAL: i18n.t("options.density_normal", "Normale"),
        COMFORT: i18n.t("options.density_comfort", "Confortable"),
    }.get(density, density)
