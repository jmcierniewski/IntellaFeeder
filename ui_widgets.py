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
