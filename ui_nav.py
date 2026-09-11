"""Navigation et repères permanents : fil d'étapes, barre de contexte, barre d'état.

Direction « Parcours », choisie le 11/09/2026. Les six destinations ne sont plus
six onglets de même rang : le travail se lit comme **deux étapes** — lire le cas,
puis y importer des sources — et les quatre écrans qui ne sont pas le parcours
(Détail, Profils, Maintenance, Aide) passent à droite, en outils.

⚠ **Le ``ttk.Notebook`` est conservé sous cette barre**, seulement privé de ses
onglets (style ``Headless.TNotebook``, cf. ``ui_theme``). Rien de ce qui touche
aux pages ne change : ``notebook.select``, ``aller_a``, le grisage d'un cas
compound par ``notebook.tab(state="disabled")`` et les sous-onglets continuent de
fonctionner tels quels. Une barre maison qui aurait aussi remplacé le Notebook
aurait demandé de réécrire tout cela pour un gain nul.

⚠ **Il y a DEUX étapes, pas trois.** Un premier jet en comptait une troisième
(« Import »), qui ouvrait la même page que « Sources » : à l'usage, elle faisait
doublon sans rien montrer de neuf (constat du 11/09/2026). Ce que le fil apporte
n'est donc pas une navigation de plus mais un **état d'avancement** — cas lu ?
import vérifié ? — qui répond à la question posée le 10/09/2026 : par où
commence-t-on ?
"""

import tkinter as tk
from tkinter import ttk

import config
import i18n
import ui_theme

# États d'une étape.
TODO, CURRENT, DONE, BLOCKED = "todo", "current", "done", "blocked"

_NUM = ("①", "②")          # une par étape
_DONE_GLYPH = "✓"                    # ✓


class _Clickable:
    """Mixin : rend un ensemble de widgets cliquable et survolable d'un bloc.

    Un « bouton » de cette barre est un Frame qui contient deux ou trois Labels.
    Sans liaison sur *chacun* d'eux, cliquer sur le libellé plutôt que sur le
    fond ne déclencherait rien — défaut classique et déroutant.
    """

    def _bind_all(self, widgets, on_click, on_enter=None, on_leave=None):
        for w in widgets:
            w.bind("<Button-1>", on_click)
            if on_enter:
                w.bind("<Enter>", on_enter)
            if on_leave:
                w.bind("<Leave>", on_leave)
            try:
                w.configure(cursor="hand2")
            except tk.TclError:
                pass


class ContextBar(tk.Frame, _Clickable):
    """Ligne de rappel du cas courant (décision D2).

    Remplace le bandeau « Paramètres communs », qui occupait deux lignes sur
    **chacun** des six écrans pour des valeurs en lecture seule : l'utilisateur
    vient de ``case.xml``, IntellaCmd.exe est verrouillé par le ``.ini`` dès
    qu'il a été renseigné une fois. Les deux restent consultables et modifiables
    par « Modifier… », qui déplie le détail sous la barre.
    """

    def __init__(self, parent, app):
        super().__init__(parent, background=config.UI_SURFACE,
                         highlightthickness=0, bd=0)
        self.app = app
        self._open = False

        self.line = tk.Frame(self, background=config.UI_SURFACE)
        self.line.pack(fill="x")
        tk.Frame(self, height=1, background=config.UI_LINE).pack(fill="x")

        self._key(i18n.t("ctx.case", "CAS"))
        self.lbl_case = self._val("—", bold=True)
        self.lbl_path = self._val("", mono=True, muted=True)
        self._sep()
        self._key(i18n.t("ctx.user", "UTILISATEUR"))
        self.lbl_user = self._val("—", bold=True)
        self._sep()
        self._key(i18n.t("ctx.exe", "INTELLACMD"))
        self.lbl_exe = self._val("—", bold=True)

        self.btn_more = tk.Label(self.line, text=i18n.t("ctx.edit", "Modifier…"),
                                 background=config.UI_SURFACE, foreground=config.ACCENT,
                                 font=ui_theme.F_SMALL, padx=8)
        self.btn_more.pack(side="left")
        self._bind_all([self.btn_more], lambda e: self.toggle(),
                       lambda e: self.btn_more.configure(font=ui_theme.F_BOLD),
                       lambda e: self.btn_more.configure(font=ui_theme.F_SMALL))

        # Volet dépliable : les champs eux-mêmes (rarement touchés).
        self.detail = tk.Frame(self, background=config.UI_SURFACE_2)

    # -- construction de la ligne -------------------------------------- #
    def _key(self, text):
        tk.Label(self.line, text=text, background=config.UI_SURFACE,
                 foreground=config.UI_INK_3, font=ui_theme.F_SMALL,
                 padx=0).pack(side="left", padx=(10, 5))

    def _val(self, text, bold=False, mono=False, muted=False):
        lbl = tk.Label(self.line, text=text, background=config.UI_SURFACE,
                       foreground=config.UI_INK_2 if muted else config.UI_INK,
                       font=ui_theme.F_MONO if mono else
                       (ui_theme.F_BOLD if bold else ui_theme.F_BODY),
                       anchor="w")
        lbl.pack(side="left")
        return lbl

    def _sep(self):
        tk.Frame(self.line, width=1, height=14,
                 background=config.UI_LINE).pack(side="left", padx=10, pady=5)

    # -- mise à jour ---------------------------------------------------- #
    def refresh(self, case_name="", case_path="", user="", exe=""):
        tiret = "—"
        self.lbl_case.configure(
            text=case_name or i18n.t("ctx.no_case", "aucun cas sélectionné"),
            foreground=config.UI_INK if case_name else config.WARN_COLOR)
        self.lbl_path.configure(text=_elide_left(case_path, 62))
        self.lbl_user.configure(text=user or tiret)
        self.lbl_exe.configure(
            text=i18n.t("ctx.exe_ok", "configuré") if exe
            else i18n.t("ctx.exe_missing", "à renseigner"),
            foreground=config.UI_INK if exe else config.WARN_COLOR)

    def toggle(self):
        self._open = not self._open
        if self._open:
            self.detail.pack(fill="x", before=None)
        else:
            self.detail.pack_forget()


class StepNav(tk.Frame, _Clickable):
    """Fil d'étapes (① Le cas → ② Import des sources) + outils à droite."""

    def __init__(self, parent, app, on_select):
        super().__init__(parent, background=config.UI_SURFACE,
                         highlightthickness=0, bd=0)
        self.app = app
        self._on_select = on_select
        self._steps = {}     # index -> dict(widgets, state, target)
        self._tools = {}     # tab id -> dict(widgets, enabled)
        self._active = None

        self.row = tk.Frame(self, background=config.UI_SURFACE)
        self.row.pack(fill="x")
        tk.Frame(self, height=1, background=config.UI_LINE).pack(fill="x")

        # DEUX étapes, et non trois (11/09/2026). « Sources » et « Import »
        # ouvraient la même page : le troisième repère ne menait nulle part de
        # neuf et faisait doublon — c'est le constat de l'utilisateur à l'usage.
        self._add_step(0, "inventaire", i18n.t("step.case", "Le cas"),
                       i18n.t("step.case_sub", "lire ce qui est déjà là"))
        self._add_step(1, "import", i18n.t("step.sources", "Import des sources"),
                       i18n.t("step.sources_sub", "coller, mesurer, importer"))

        tk.Frame(self.row, background=config.UI_SURFACE).pack(side="left", expand=True, fill="x")

        for tab_id, label in (("detail", i18n.t("tabs.detail_short", "Détail")),
                              ("profils", i18n.t("tabs.profiles", "Profils")),
                              ("maintenance", i18n.t("tabs.maintenance", "Maintenance")),
                              ("aide", i18n.t("tabs.help", "Aide"))):
            self._add_tool(tab_id, label)

    # -- construction --------------------------------------------------- #
    def _add_step(self, index, target, titre, sous_titre):
        box = tk.Frame(self.row, background=config.UI_SURFACE)
        box.pack(side="left", fill="y")

        inner = tk.Frame(box, background=config.UI_SURFACE)
        inner.pack(fill="both", expand=True, padx=0)

        num = tk.Label(inner, text=_NUM[index], background=config.UI_SURFACE,
                       foreground=config.UI_INK_3, font=ui_theme.F_STEP)
        num.pack(side="left", padx=(14, 8), pady=5)

        texts = tk.Frame(inner, background=config.UI_SURFACE)
        texts.pack(side="left", padx=(0, 16), pady=4)
        lbl = tk.Label(texts, text=titre, background=config.UI_SURFACE,
                       foreground=config.UI_INK_2, font=ui_theme.F_BOLD, anchor="w")
        lbl.pack(anchor="w")
        sub = tk.Label(texts, text=sous_titre, background=config.UI_SURFACE,
                       foreground=config.UI_INK_3, font=ui_theme.F_SMALL, anchor="w")
        sub.pack(anchor="w")

        rule = tk.Frame(box, height=2, background=config.UI_SURFACE)
        rule.pack(fill="x", side="bottom")

        sep = tk.Frame(self.row, width=1, background=config.UI_LINE_SOFT)
        sep.pack(side="left", fill="y", pady=6)

        widgets = [box, inner, num, texts, lbl, sub]
        self._steps[index] = {"box": box, "inner": inner, "num": num, "texts": texts,
                              "lbl": lbl, "sub": sub, "rule": rule, "all": widgets,
                              "state": TODO, "target": target, "index": index}
        self._bind_all(widgets, lambda e, i=index: self._click_step(i))

    def _add_tool(self, tab_id, label):
        box = tk.Frame(self.row, background=config.UI_SURFACE)
        box.pack(side="left", fill="y")
        lbl = tk.Label(box, text=label, background=config.UI_SURFACE,
                       foreground=config.UI_INK_2, font=ui_theme.F_BODY,
                       padx=11, pady=5)
        lbl.pack(fill="both", expand=True)
        rule = tk.Frame(box, height=2, background=config.UI_SURFACE)
        rule.pack(fill="x", side="bottom")
        self._tools[tab_id] = {"box": box, "lbl": lbl, "rule": rule,
                               "all": [box, lbl], "enabled": True}
        self._bind_all([box, lbl], lambda e, t=tab_id: self._click_tool(t))

    # -- interactions ---------------------------------------------------- #
    def _click_step(self, index):
        st = self._steps[index]
        if st["state"] == BLOCKED:
            return
        self._on_select(st["target"], index)

    def _click_tool(self, tab_id):
        if self._tools[tab_id]["enabled"]:
            self._on_select(tab_id, None)

    # -- état ------------------------------------------------------------ #
    def set_step_state(self, index, state):
        st = self._steps.get(index)
        if not st or st["state"] == state:
            return
        st["state"] = state
        self._paint_step(index)

    def set_active(self, tab_id, step_index=None):
        """Met en avant l'étape ou l'outil correspondant à la page affichée."""
        self._active = (tab_id, step_index)
        for i in self._steps:
            self._paint_step(i)
        for t in self._tools:
            self._paint_tool(t)

    def set_enabled(self, tab_id, enabled: bool):
        """Grise les étapes 2 et 3 sur un cas compound (import impossible)."""
        for i, st in self._steps.items():
            if st["target"] == tab_id:
                st["state"] = BLOCKED if not enabled else TODO
                self._paint_step(i)
        if tab_id in self._tools:
            self._tools[tab_id]["enabled"] = enabled
            self._paint_tool(tab_id)

    def _is_active_step(self, index):
        if not self._active:
            return False
        tab_id, step = self._active
        st = self._steps[index]
        if st["target"] != tab_id:
            return False
        # Une page visée sans étape précise (ex. retour sur l'Import par un
        # bouton) met en avant la PREMIÈRE étape qui lui correspond.
        if step is None:
            return index == min(i for i, s in self._steps.items() if s["target"] == tab_id)
        return index == step

    def _paint_step(self, index):
        st = self._steps[index]
        actif = self._is_active_step(index)
        etat = st["state"]
        if etat == BLOCKED:
            bg, ink, sub_ink, num_ink, rule = (
                config.UI_SURFACE, config.UI_INK_3, config.UI_INK_3, config.UI_INK_3,
                config.UI_SURFACE)
            st["num"].configure(text=_NUM[index])
        elif actif:
            bg, ink, sub_ink, num_ink, rule = (
                config.ACCENT_SOFT, config.ACCENT, config.UI_INK_2, config.ACCENT,
                config.ACCENT)
            st["num"].configure(text=_NUM[index])
        elif etat == DONE:
            bg, ink, sub_ink, num_ink, rule = (
                config.UI_SURFACE, config.UI_INK, config.UI_INK_3,
                config.ACTION_COLOR, config.UI_SURFACE)
            st["num"].configure(text=_DONE_GLYPH)
        else:
            bg, ink, sub_ink, num_ink, rule = (
                config.UI_SURFACE, config.UI_INK_2, config.UI_INK_3,
                config.UI_INK_3, config.UI_SURFACE)
            st["num"].configure(text=_NUM[index])
        for w in (st["box"], st["inner"], st["texts"]):
            w.configure(background=bg)
        st["num"].configure(background=bg, foreground=num_ink)
        st["lbl"].configure(background=bg, foreground=ink)
        st["sub"].configure(background=bg, foreground=sub_ink)
        st["rule"].configure(background=rule)

    def _paint_tool(self, tab_id):
        t = self._tools[tab_id]
        actif = bool(self._active) and self._active[0] == tab_id
        if not t["enabled"]:
            bg, ink, rule = config.UI_SURFACE, config.UI_INK_3, config.UI_SURFACE
        elif actif:
            bg, ink, rule = config.ACCENT_SOFT, config.ACCENT, config.ACCENT
        else:
            bg, ink, rule = config.UI_SURFACE, config.UI_INK_2, config.UI_SURFACE
        t["box"].configure(background=bg)
        t["lbl"].configure(background=bg, foreground=ink,
                           font=ui_theme.F_BOLD if actif else ui_theme.F_BODY)
        t["rule"].configure(background=rule)


class StatusBar(tk.Frame):
    """Bandeau permanent du bas (décision D10) : état, puis résumé du cas.

    Ce qui s'y trouve était dispersé — deux lignes de texte gris au-dessus des
    boutons de l'Import, un titre au-dessus du tableau de l'Inventaire — et
    disparaissait dès qu'on changeait d'écran.
    """

    LEVELS = {"ok": config.ACTION_COLOR, "warn": config.WARN_COLOR,
              "error": config.DANGER_COLOR, "busy": config.ACCENT}

    def __init__(self, parent, app):
        super().__init__(parent, background=config.UI_SURFACE,
                         highlightthickness=0, bd=0)
        self.app = app
        tk.Frame(self, height=1, background=config.UI_LINE).pack(fill="x")
        row = tk.Frame(self, background=config.UI_SURFACE)
        row.pack(fill="x")

        self.dot = tk.Label(row, text="●", background=config.UI_SURFACE,
                            foreground=config.ACTION_COLOR, font=ui_theme.F_SMALL)
        self.dot.pack(side="left", padx=(10, 6), pady=2)
        self.lbl = tk.Label(row, text="", background=config.UI_SURFACE,
                            foreground=config.UI_INK_2, font=ui_theme.F_SMALL, anchor="w")
        self.lbl.pack(side="left")
        self.lbl_right = tk.Label(row, text="", background=config.UI_SURFACE,
                                  foreground=config.UI_INK_3, font=ui_theme.F_SMALL,
                                  anchor="e")
        self.lbl_right.pack(side="right", padx=10)

    def set_status(self, text: str, level: str = "ok"):
        self.dot.configure(foreground=self.LEVELS.get(level, config.ACTION_COLOR))
        self.lbl.configure(text=text or "")

    def set_summary(self, text: str):
        self.lbl_right.configure(text=text or "")


def _elide_left(texte: str, maxi: int) -> str:
    """Tronque par la GAUCHE : sur un chemin, c'est la fin qui identifie le cas."""
    texte = texte or ""
    if len(texte) <= maxi:
        return texte
    return "…" + texte[-(maxi - 1):]
