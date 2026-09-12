"""Petits widgets réutilisables : infobulles, boutons, fenêtres, lecteurs.

⚠ ``show_mime_filter`` a été RETIRÉ le 11/09/2026 : son contenu — les deux
panneaux du filtre de types — est devenu le sous-onglet « Types de fichiers à
indexer » (``ui_types_panel``). Il restait un popup de plus qui faisait doublon
avec un onglet, et les deux ne se parlaient pas.

Reste ici ``show_source_settings`` : les réglages d'une source, à une autre
échelle (une vingtaine d'entrées contre plusieurs centaines) et avec un autre
propos. Ne pas fondre les deux vues en une seule.
"""

import tkinter as tk
from tkinter import ttk

import config
import i18n
import mime_catalog
import profile_translate
import ui_theme

# --- Filtre de types MIME : trois états, trois couleurs ------------------- #
# Un filtre réel compte plusieurs centaines d'entrées, et **18 % d'entre elles
# ne sont pas décrites** par le fichier livré par Vound : ce sont des alias
# qu'Intella écrit sans les nommer (cf. `mime_catalog`). Le rouge est donc
# réservé à ce qu'on n'a **jamais vu** — sinon il couvrirait la moitié de la
# liste et ne voudrait plus rien dire.
MIME_STATUS_COLORS = {
    mime_catalog.STATUS_DESCRIBED: "#1d4ed8",   # bleu : nommé par le référentiel
    mime_catalog.STATUS_OBSERVED: "#111827",    # noir : vu chez Intella, non décrit
    mime_catalog.STATUS_UNKNOWN: "#b91c1c",     # rouge : jamais vu, à vérifier
    # Turquoise : décrit par VOUS, pas par Vound. Distinct du bleu pour qu'on
    # sache d'un coup d'œil ce qui vient du référentiel et ce qu'on a écrit.
    mime_catalog.STATUS_USER: "#0f766e",
}


# --- Réglages d'une source : trois états, trois couleurs ------------------ #
# ⚠ **Même code couleur que les types MIME ci-dessus, autre échelle** : ici une
# vingtaine de réglages, là plusieurs centaines de types. Ne pas fondre les deux
# vues (cf. CLAUDE.md, Étude 4).
# 🐞 Ce dictionnaire avait DISPARU le 11/09/2026 en même temps que
# `show_mime_filter` : la fenêtre « Voir les réglages de la source… » levait un
# NameError juste après son en-tête, et s'ouvrait donc **vide** — un grand
# panneau avec deux lignes dedans, sans la moindre erreur visible.
SETTING_STATUS_COLORS = {
    profile_translate.STATUS_MAPPED: "#1d4ed8",       # bleu : rejoué par le profil
    profile_translate.STATUS_UNSUPPORTED: "#111827",  # noir : à refaire dans Intella
    profile_translate.STATUS_UNKNOWN: "#b91c1c",      # rouge : nom inconnu
}


def mime_status_label(etat: str) -> str:
    """Libellé traduit d'un état de `mime_catalog` (module sans i18n)."""
    return {
        mime_catalog.STATUS_DESCRIBED: i18n.t("mime.state_described", "décrit"),
        # ⚠ Libellé revu le 11/09/2026. Il disait « vu dans vos cas », ce qui a
        # fait croire que le type était **dans le cas courant** — il n'en est
        # rien : ce sont les 800 noms embarqués plus ceux appris des exports
        # déjà lus. L'information utile est qu'il manque un libellé.
        mime_catalog.STATUS_OBSERVED: i18n.t("mime.state_observed",
                                             "connu, sans libellé"),
        mime_catalog.STATUS_UNKNOWN: i18n.t("mime.state_unknown", "inconnu"),
        mime_catalog.STATUS_USER: i18n.t("mime.state_user", "décrit par vous"),
    }.get(etat, etat)


def mime_filter_sense(mode: str) -> str:
    r"""Phrase disant ce que la liste FAIT — sans elle, on la lit à l'envers.

    Le piège est réel et coûteux : dans l'interface d'Intella on coche ce qu'on
    **veut**, et le XML enregistre le **complément** — d'où
    ``<includeMode>Exclude selected entries</includeMode>`` suivi de 600 types.
    Moins on coche, plus la liste est longue. Afficher les types sans dire leur
    sens laisse croire qu'on regarde ce qui sera indexé, alors que c'est
    exactement l'inverse.
    """
    if (mode or "").strip().lower().startswith("include"):
        return i18n.t("mime.sense_include",
                      "SEULS ces types sont indexés (les autres sont écartés).")
    return i18n.t("mime.sense_exclude",
                  "Ces types sont EXCLUS de l'indexation ; tout le reste est indexé.")


def mime_filter_summary(texte: str, mode: str = "", avec_sens: bool = True) -> str:
    """Résumé d'un filtre en une ligne, **sens compris** par défaut.

    ``avec_sens=False`` quand l'appelant affiche déjà le sens à part (fenêtre de
    lecture) : le répéter deux fois à trois lignes d'écart ne l'éclaire pas.
    """
    if not (texte or "").strip():
        # Un mode « include » sans liste ne veut rien dire et n'est pas émis
        # (cf. `profile_catalog.diff_from_default`) : le dire, sinon le combo
        # laisse croire à un réglage actif.
        if (mode or "").strip().lower().startswith("include"):
            return i18n.t(
                "mime.filter_none_include",
                "Aucun filtre : le mode « include » reste sans effet tant que la "
                "liste est vide — tous les types sont indexés.")
        return i18n.t("mime.filter_none", "Aucun filtre (tous les types indexés).")
    r = mime_catalog.summarize_filter(texte)
    resume = i18n.t("mime.filter_summary",
                    "{t} type(s) — {d} décrit(s), {o} sans libellé",
                    t=r["total"], d=r[mime_catalog.STATUS_DESCRIBED],
                    o=r[mime_catalog.STATUS_OBSERVED])
    if r[mime_catalog.STATUS_UNKNOWN]:
        resume += ", " + i18n.t("mime.filter_unknown", "{n} inconnu(s)",
                                n=r[mime_catalog.STATUS_UNKNOWN])
    resume += "."
    return resume + " " + mime_filter_sense(mode) if avec_sens else resume


def setting_status_label(etat: str) -> str:
    """Libellé traduit d'un état de `profile_translate` (module sans i18n)."""
    return {
        profile_translate.STATUS_MAPPED:
            i18n.t("settings.state_mapped", "rejoué par le profil"),
        profile_translate.STATUS_UNSUPPORTED:
            i18n.t("settings.state_unsupported", "à refaire dans Intella"),
        profile_translate.STATUS_UNKNOWN:
            i18n.t("settings.state_unknown", "inconnu — à vérifier"),
    }.get(etat, etat)


def setting_reason_label(motif: str) -> str:
    """Motif de non-rejouabilité, en clair."""
    return {
        profile_translate.REASON_NOT_IN_API: i18n.t(
            "settings.reason_not_in_api",
            "Intella n'accepte pas ce réglage à l'import automatique."),
        profile_translate.REASON_SCRIPT_INCOMPLETE: i18n.t(
            "settings.reason_script",
            "L'export ne contient pas le fichier de script : le rejouer armerait "
            "un script absent."),
    }.get(motif, "")


def settings_summary(src: dict) -> str:
    """Résumé en une ligne des réglages d'une source (pour un bandeau)."""
    r = profile_translate.summarize_settings(src)
    if not r["total"]:
        return i18n.t("settings.summary_none",
                      "Cette source n'expose aucun réglage dans l'export.")
    resume = i18n.t(
        "settings.summary",
        "{t} réglage(s) — {m} rejoué(s) par le profil, {u} à refaire dans Intella",
        t=r["total"], m=r[profile_translate.STATUS_MAPPED],
        u=r[profile_translate.STATUS_UNSUPPORTED])
    if r[profile_translate.STATUS_UNKNOWN]:
        resume += ", " + i18n.t("settings.summary_unknown", "{n} inconnu(s)",
                                n=r[profile_translate.STATUS_UNKNOWN])
    return resume + "."


def show_source_settings(parent, src: dict, titre: str = "") -> None:
    """Fenêtre de lecture de **tous** les réglages d'une source exportée.

    C'est la vue qui remplace le passe-plat abandonné (Étude 3 du CLAUDE.md) :
    `-addSourcesFromJson` travaille sur une liste blanche de noms et jette en
    silence tout le reste — impossible, donc, de rejouer un réglage qu'il ne
    connaît pas. À défaut de tout rejouer, on **montre** : l'utilisateur voit
    d'un coup d'œil ce que le profil reprend (bleu) et ce qu'il lui reste à
    refaire à la main dans Intella (noir).

    Le rouge est le signal d'une version d'Intella plus récente : un nom qui
    n'est ni au catalogue ni dans la table des non-rejouables est apparu depuis.
    """
    win = make_dialog(parent, titre or i18n.t("settings.title", "Réglages de la source"),
                      "1130x620")

    ttk.Label(win, wraplength=910, justify="left", font=ui_theme.F_BOLD,
              text=i18n.t(
                  "settings.header",
                  "Un profil ne rejoue que les réglages qu'Intella accepte à "
                  "l'import automatique. Les autres sont à refaire à la main.")
              ).pack(anchor="w", padx=10, pady=(10, 2))
    ttk.Label(win, text=settings_summary(src)).pack(anchor="w", padx=10, pady=(0, 6))

    # Chaque état porte son explication (demande du 11/09/2026) : les trois
    # libellés sont justes mais muets — « à refaire dans Intella » ne dit ni
    # pourquoi, ni ce qu'il faut faire, et « inconnu » se lit comme une erreur
    # alors que c'est le plus souvent le signe d'un Intella plus récent.
    aides = {
        profile_translate.STATUS_MAPPED: i18n.t(
            "settings.tip_mapped",
            "Ce réglage fait partie des options qu'IntellaCmd accepte à l'import "
            "automatique. Enregistré dans le profil, il sera réappliqué tel quel "
            "à chaque source qui utilise ce profil. Vous n'avez rien à faire."),
        profile_translate.STATUS_UNSUPPORTED: i18n.t(
            "settings.tip_unsupported",
            "Intella sait enregistrer ce réglage, mais son import automatique ne "
            "l'accepte pas : la commande le jette en silence. Un profil ne peut "
            "donc pas le rejouer.\n\nÀ faire : après l'import, ouvrez la source "
            "dans Intella et remettez ce réglage à la main — ou acceptez la "
            "valeur par défaut."),
        profile_translate.STATUS_UNKNOWN: i18n.t(
            "settings.tip_unknown",
            "Ce nom de réglage n'est ni dans la liste des options pilotables, ni "
            "dans celle des réglages connus mais non rejouables. C'est presque "
            "toujours le signe d'une version d'Intella plus récente que ce que "
            "l'application connaît.\n\nÀ faire : vérifiez dans Intella ce que ce "
            "réglage vaut pour vos sources. Il n'y a rien de cassé."),
    }
    legende = ttk.Frame(win)
    legende.pack(fill="x", padx=10, pady=(0, 6))
    for etat in (profile_translate.STATUS_MAPPED,
                 profile_translate.STATUS_UNSUPPORTED,
                 profile_translate.STATUS_UNKNOWN):
        pastille = tk.Label(legende, text="■ " + setting_status_label(etat) + " ⓘ",
                            fg=SETTING_STATUS_COLORS[etat], cursor="question_arrow")
        pastille.pack(side="left", padx=(0, 16))
        attach_tip(pastille, aides[etat])

    holder = ttk.Frame(win)
    holder.pack(fill="both", expand=True, padx=10, pady=(0, 10))
    # ⚠ Le MOTIF a sa propre colonne. Accolé à l'état, il donnait une cellule de
    # 90 caractères dans une colonne de 190 pixels : « à refaire dans Intella —
    # Intella n'acce… », c'est-à-dire l'information utile coupée juste avant.
    tree = ttk.Treeview(holder,
                        columns=("key", "label", "value", "state", "why"),
                        show="headings")
    for col, entete, largeur in (
            ("key", i18n.t("settings.col_key", "Réglage (nom Intella)"), 210),
            ("label", i18n.t("settings.col_label", "Description"), 260),
            ("value", i18n.t("settings.col_value", "Valeur"), 110),
            ("state", i18n.t("settings.col_state", "État"), 170),
            ("why", i18n.t("settings.col_why", "Pourquoi"), 330)):
        tree.heading(col, text=entete)
        tree.column(col, width=largeur, anchor="w")
    vsb = ttk.Scrollbar(holder, orient="vertical", command=tree.yview)
    tree.configure(yscrollcommand=vsb.set)
    tree.pack(side="left", fill="both", expand=True)
    vsb.pack(side="right", fill="y")
    for etat, couleur in SETTING_STATUS_COLORS.items():
        tree.tag_configure(etat, foreground=couleur)

    for ligne in profile_translate.describe_settings(src):
        tree.insert("", "end", tags=(ligne["status"],),
                    values=(ligne["xml_key"], ligne["label"],
                            ligne["value"] or "—",
                            setting_status_label(ligne["status"]),
                            setting_reason_label(ligne["reason"])))

    make_button(win, i18n.t("common.close", "Fermer"), win.destroy).pack(
        anchor="e", padx=10, pady=(0, 10))


# --- Boutons : apparence unique pour toute l'application ----------------- #
# tk.Button (et non ttk.Button) : sous le thème Windows, le FOND d'un ttk.Button
# n'est pas modifiable → on ne pourrait pas contraster/colorer. On centralise ici
# pour que tous les boutons aient le même look.
#
# v3.0 — DEUX NIVEAUX, pas un seul (11/09/2026). Jusque-là tout bouton était un
# aplat plein : sur un panneau de dix boutons, le bouton d'action se noyait dans
# neuf autres de même poids. Un bouton coloré est désormais **plein** (l'action,
# le danger), un bouton neutre est **en contour** (fond clair, texte sombre,
# filet). La règle « une seule action colorée par panneau » y gagne enfin un
# contraste qui se voit.
BTN_DEFAULT_BG = "#475569"   # conservé : repli si le thème n'est pas actif
BTN_OUTLINE_BG = config.UI_SURFACE
BTN_OUTLINE_FG = config.UI_INK
BTN_OUTLINE_LINE = "#9fadba"


def _darken(hex_color: str, factor: float = 0.82) -> str:
    """Assombrit une couleur ``#rrggbb`` (pour l'état actif/pressé)."""
    try:
        h = hex_color.lstrip("#")
        r, g, b = (int(h[i:i + 2], 16) for i in (0, 2, 4))
        r, g, b = (max(0, int(c * factor)) for c in (r, g, b))
        return f"#{r:02x}{g:02x}{b:02x}"
    except (ValueError, IndexError):
        return hex_color


def make_button(parent, text, command, color: str = None, fg: str = "white",
                outline: str = None, **kw):
    """Bouton à l'apparence standard de l'application.

    - sans ``color`` ni ``outline`` : bouton **neutre en contour** (le cas le
      plus fréquent) ;
    - ``color`` : bouton **plein** de cette couleur — réservé aux quatre rôles
      de ``config`` (action, danger, alerte, renvoi vers un autre onglet) ;
    - ``outline`` : bouton **en contour coloré**, pour un renvoi discret vers un
      autre onglet sans concurrencer l'action du panneau.

    ``kw`` surcharge tout attribut tk.Button (ex. ``state``, ``width``). Le
    bouton est enregistré auprès du thème actif : son rembourrage suit la
    densité choisie dans Maintenance → Options, sans redémarrage.
    """
    if color:
        bg, texte, bordure = color, fg, color
        actif = _darken(color)
    elif outline:
        bg, texte, bordure = config.UI_SURFACE, outline, outline
        actif = config.ACCENT_SOFT
    else:
        bg, texte, bordure = BTN_OUTLINE_BG, BTN_OUTLINE_FG, BTN_OUTLINE_LINE
        actif = config.UI_SURFACE_2
    style = dict(
        # Bordure : `highlightthickness` et non `relief="solid"` — un relief
        # solid se dessine en noir dur, quelle que soit la couleur voulue.
        font=ui_theme.F_BTN, bg=bg, fg=texte, activebackground=actif,
        activeforeground=texte, relief="flat", bd=0,
        highlightthickness=1, highlightbackground=bordure, highlightcolor=bordure,
        padx=10, pady=3, cursor="hand2", disabledforeground="#b6c0ca",
    )
    style.update(kw)
    btn = tk.Button(parent, text=text, command=command, **style)
    theme = ui_theme.current()
    if theme is not None:
        theme.register_button(btn)
    return btn


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
            self, "✕", None, color=config.DANGER_COLOR, padx=6, pady=0)
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

    def start_busy(self, text: str, on_cancel=None, cancel_text: str = "✕ Annuler"):
        """Affiche le bandeau en mode indéterminé (attente de durée inconnue).

        ``on_cancel`` sert aux attentes longues dont on ignore le total mais
        qu'on doit pouvoir interrompre — l'exploration d'un dossier de scellés
        sur partage réseau, par exemple. Sans lui, pas de bouton (le re-scan de
        « Valider les opérations » n'est pas interruptible).
        """
        self._on_cancel = on_cancel
        if on_cancel:
            self.btn_cancel.config(text=cancel_text, command=self._cancel, state="normal")
            self.btn_cancel.pack(side="left", padx=4)
        else:
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


def make_dialog(parent, titre: str, geometry: str = "") -> tk.Toplevel:
    """Fenêtre secondaire **réductible**, au look de l'application.

    ⚠ Pas de ``transient()`` — et c'est le point (demande du 11/09/2026).
    Sous Windows, une fenêtre marquée transitoire devient une *fenêtre outil* :
    elle perd son bouton Réduire et n'apparaît plus dans la barre des tâches.
    Or ces fenêtres-là — le filtre de types, les réglages d'une source, la
    vérification d'import — se consultent en allant et venant avec la fenêtre
    principale ; ne pouvoir que les fermer oblige à tout rouvrir.

    Ce qu'on perd : elles ne restent plus au-dessus du parent. C'est le prix
    d'un bouton Réduire, et c'est ce qui a été demandé.
    """
    win = tk.Toplevel(parent)
    win.title(titre)
    if geometry:
        win.geometry(geometry)
    win.configure(background=config.UI_BG)
    try:
        win.iconbitmap(config.resource_path("intella.ico"))
    except tk.TclError:
        pass                       # icône absente : sans importance
    win.bind("<Escape>", lambda _e: win.destroy())
    return win


def attach_tip(widget, texte: str, delai: int = 450):
    """Attache une infobulle à un widget. Le moyen standard dans l'application.

    Chaque appelant créait jusque-là sa propre paire ``<Enter>``/``<Leave>``
    autour d'un ``Tooltip`` partagé, ce qui rendait l'ajout d'une infobulle plus
    coûteux qu'il ne devrait — donc rare. Le délai évite qu'une bulle surgisse au
    moindre passage de souris sur une barre d'outils dense.
    """
    if not texte:
        return
    etat = {"tip": None, "after": None}

    def _montrer(x, y):
        etat["after"] = None
        if etat["tip"] is not None:
            return
        try:
            tip = tk.Toplevel(widget)
        except tk.TclError:
            return
        tip.wm_overrideredirect(True)
        tip.wm_geometry(f"+{x}+{y}")
        tk.Label(tip, text=texte, background="#fffbe6", foreground=config.UI_INK,
                 relief="solid", borderwidth=1, justify="left", padx=7, pady=4,
                 font=ui_theme.F_SMALL, wraplength=460).pack()
        etat["tip"] = tip

    def _entrer(e):
        _quitter(None)
        etat["after"] = widget.after(delai, lambda: _montrer(e.x_root + 14, e.y_root + 22))

    def _quitter(_e):
        if etat["after"] is not None:
            try:
                widget.after_cancel(etat["after"])
            except tk.TclError:
                pass
            etat["after"] = None
        if etat["tip"] is not None:
            try:
                etat["tip"].destroy()
            except tk.TclError:
                pass
            etat["tip"] = None

    widget.bind("<Enter>", _entrer, add="+")
    widget.bind("<Leave>", _quitter, add="+")
    widget.bind("<Button-1>", _quitter, add="+")
    widget.bind("<Destroy>", _quitter, add="+")


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
