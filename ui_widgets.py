"""Petits widgets réutilisables (infobulle, boutons à look unifié)."""

import tkinter as tk
from tkinter import ttk

# --- Boutons : apparence unique pour toute l'application ----------------- #
# tk.Button (et non ttk.Button) : sous le thème Windows, le FOND d'un ttk.Button
# n'est pas modifiable → on ne pourrait pas contraster/colorer. On centralise ici
# pour que tous les boutons aient le même look.
BTN_FONT = ("Segoe UI", 9, "bold")
BTN_DEFAULT_BG = "#475569"   # slate-600 : contrasté sur fond clair, texte blanc


def _darken(hex_color: str, factor: float = 0.82) -> str:
    """Assombrit une couleur ``#rrggbb`` (pour l'état actif/pressé)."""
    try:
        h = hex_color.lstrip("#")
        r, g, b = (int(h[i:i + 2], 16) for i in (0, 2, 4))
        r, g, b = (max(0, int(c * factor)) for c in (r, g, b))
        return f"#{r:02x}{g:02x}{b:02x}"
    except (ValueError, IndexError):
        return hex_color


def make_button(parent, text, command, color: str = None, fg: str = "white", **kw):
    """Bouton à l'apparence standard de l'application (contrasté, colorable).

    ``color`` : fond du bouton (défaut = slate). ``kw`` surcharge tout attribut
    tk.Button (ex. ``state``, ``width``).
    """
    bg = color or BTN_DEFAULT_BG
    style = dict(
        font=BTN_FONT, bg=bg, fg=fg, activebackground=_darken(bg),
        activeforeground=fg, relief="raised", bd=1, padx=10, pady=3,
        cursor="hand2", highlightthickness=0, disabledforeground="#cbd5e1",
    )
    style.update(kw)
    return tk.Button(parent, text=text, command=command, **style)


class MeasureBar(ttk.Frame):
    """Bandeau de progression d'une mesure longue : barre + détail + « Annuler ».

    Partagé par l'onglet Import (« Calculer la taille ») et l'onglet Inventaire
    (« Scanner les dossiers à 0 ») : les deux scannent des volumes réseau où une
    source peut demander des dizaines de minutes.

    Pas d'ETA : connaître le total exigerait un pré-parcours aussi coûteux que la
    mesure. On affiche ce qui est mesurable sans surcoût — élément i/n, fichiers
    parcourus, octets cumulés, temps écoulé, débit — ce qui suffit à juger de
    l'ordre de grandeur au bout de quelques secondes.

    Mode indéterminé (``start_busy``) pour les attentes dont on ne connaît pas
    l'avancement (re-scan IntellaCmd de « Valider les opérations »).
    """

    def __init__(self, parent, pack_opts: dict = None, **kw):
        super().__init__(parent, **kw)
        # Options de placement mémorisées : le bandeau est masqué au repos, il
        # doit se réafficher au même endroit (ex. juste avant le total).
        self._pack_opts = pack_opts or {"anchor": "w", "fill": "x",
                                        "padx": 6, "pady": (0, 2)}
        self.pb = ttk.Progressbar(self, mode="determinate", length=220)
        self.pb.pack(side="left")
        self.lbl = ttk.Label(self, text="", foreground="#1e40af")
        self.lbl.pack(side="left", padx=8)
        self.btn_cancel = make_button(
            self, "✕", None, color="#b91c1c", padx=6, pady=0)
        self._packed = False
        self._on_cancel = None

    # -- cycle de vie ----------------------------------------------------- #
    def start(self, total: int, on_cancel=None, cancel_text: str = "✕ Annuler"):
        """Affiche le bandeau en mode déterminé (``total`` éléments à mesurer)."""
        self.pb.config(mode="determinate", maximum=max(1, total), value=0)
        self.pb.stop()
        self._on_cancel = on_cancel
        if on_cancel:
            self.btn_cancel.config(text=cancel_text, command=self._cancel, state="normal")
            self.btn_cancel.pack(side="left", padx=4)
        else:
            self.btn_cancel.pack_forget()
        self.lbl.config(text="")
        self._show()

    def start_busy(self, text: str):
        """Affiche le bandeau en mode indéterminé (attente de durée inconnue)."""
        self._on_cancel = None
        self.btn_cancel.pack_forget()
        self.pb.config(mode="indeterminate")
        self.lbl.config(text=text)
        self._show()
        self.pb.start(12)

    def stop(self):
        self.pb.stop()
        if self._packed:
            self.pack_forget()
            self._packed = False

    # -- mise à jour ------------------------------------------------------ #
    def set_step(self, i: int, total: int, text: str):
        self.pb.config(value=max(0, i - 1))
        self.lbl.config(text=text)

    def step_done(self):
        self.pb.config(value=self.pb.cget("value") + 1)

    def set_text(self, text: str):
        self.lbl.config(text=text)

    def cancelling(self, text: str):
        """L'annulation est demandée : bouton grisé, le worker s'arrêtera."""
        self.btn_cancel.config(state="disabled")
        self.lbl.config(text=text)

    # -- interne ---------------------------------------------------------- #
    def _cancel(self):
        if self._on_cancel:
            self._on_cancel()

    def _show(self):
        if not self._packed:
            self.pack(**self._pack_opts)
            self._packed = True


class Tooltip:
    """Infobulle légère pilotée manuellement (afficher à des coordonnées écran)."""

    def __init__(self, master):
        self.master = master
        self._tip = None
        self._text = None

    def show(self, text: str, x: int, y: int):
        if not text:
            self.hide()
            return
        if self._tip is not None and text == self._text:
            self._tip.wm_geometry(f"+{x}+{y}")
            return
        self.hide()
        self._text = text
        self._tip = tk.Toplevel(self.master)
        self._tip.wm_overrideredirect(True)
        self._tip.wm_geometry(f"+{x}+{y}")
        ttk.Label(
            self._tip, text=text, background="#ffffe0", relief="solid",
            borderwidth=1, padding=4, justify="left",
        ).pack()

    def hide(self):
        if self._tip is not None:
            self._tip.destroy()
            self._tip = None
            self._text = None
