"""Petits widgets réutilisables (infobulle, boutons, lecteurs colorés).

Deux lecteurs y cohabitent, au **même code couleur mais à deux échelles** : le
filtre de types MIME d'une source (des centaines d'entrées) et les réglages
d'indexation de cette source (une vingtaine). Ils ne se corrigent pas au même
endroit — ne pas les fondre en un seul tableau.
"""

import tkinter as tk
from tkinter import ttk

import i18n
import mime_catalog
import profile_translate

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
}


def mime_status_label(etat: str) -> str:
    """Libellé traduit d'un état de `mime_catalog` (module sans i18n)."""
    return {
        mime_catalog.STATUS_DESCRIBED: i18n.t("mime.state_described", "décrit"),
        mime_catalog.STATUS_OBSERVED: i18n.t("mime.state_observed", "vu dans vos cas"),
        mime_catalog.STATUS_UNKNOWN: i18n.t("mime.state_unknown", "inconnu"),
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
                    "{t} type(s) — {d} décrit(s), {o} vu(s) dans vos cas",
                    t=r["total"], d=r[mime_catalog.STATUS_DESCRIBED],
                    o=r[mime_catalog.STATUS_OBSERVED])
    if r[mime_catalog.STATUS_UNKNOWN]:
        resume += ", " + i18n.t("mime.filter_unknown", "{n} inconnu(s)",
                                n=r[mime_catalog.STATUS_UNKNOWN])
    resume += "."
    return resume + " " + mime_filter_sense(mode) if avec_sens else resume


def show_mime_filter(parent, texte: str, titre: str = "", mode: str = "") -> None:
    """Fenêtre de lecture d'un filtre de types : un tableau au lieu d'une chaîne.

    Une liste de 600 noms séparés par des virgules n'est pas relisible dans un
    champ de saisie — or c'est exactement ce que produit un « refine » complet
    dans Intella. Lecture seule : le filtre s'édite toujours dans son champ.

    ``mode`` (``include``/``exclude``) est affiché **en tête et en gras** : la
    liste seule se lit à l'envers une fois sur deux (cf. `mime_filter_sense`).
    """
    win = tk.Toplevel(parent)
    win.title(titre or i18n.t("mime.filter_title", "Types filtrés"))
    win.geometry("860x560")
    win.transient(parent.winfo_toplevel())

    ttk.Label(win, text=mime_filter_sense(mode),
              font=("Segoe UI", 10, "bold")).pack(anchor="w", padx=10, pady=(10, 2))
    ttk.Label(win, text=mime_filter_summary(texte, avec_sens=False)).pack(
        anchor="w", padx=10, pady=(0, 6))

    holder = ttk.Frame(win)
    holder.pack(fill="both", expand=True, padx=10, pady=(0, 10))
    tree = ttk.Treeview(holder, columns=("name", "label", "state"),
                        show="headings")
    for col, entete, largeur in (
            ("name", i18n.t("mime.col_name", "Type"), 350),
            ("label", i18n.t("mime.col_label", "Description"), 330),
            ("state", i18n.t("mime.col_state", "État"), 130)):
        tree.heading(col, text=entete)
        tree.column(col, width=largeur, anchor="w")
    vsb = ttk.Scrollbar(holder, orient="vertical", command=tree.yview)
    tree.configure(yscrollcommand=vsb.set)
    tree.pack(side="left", fill="both", expand=True)
    vsb.pack(side="right", fill="y")
    for etat, couleur in MIME_STATUS_COLORS.items():
        tree.tag_configure(etat, foreground=couleur)

    if (texte or "").strip():
        for nom, etat, libelle in mime_catalog.classify_filter(texte):
            tree.insert("", "end",
                        values=(nom or i18n.t("mime.untyped", "(sans type)"),
                                libelle, mime_status_label(etat)),
                        tags=(etat,))

    make_button(win, i18n.t("common.close", "Fermer"), win.destroy).pack(
        anchor="e", padx=10, pady=(0, 10))


# --- Réglages d'une source : trois états, trois couleurs ----------------- #
# ⚠ **Deux échelles distinctes, même code couleur** : les *réglages* d'une
# source ici, les *types MIME* d'un filtre plus haut. Ne pas les fondre dans un
# seul tableau — un filtre compte des centaines d'entrées, un jeu de réglages
# une vingtaine, et ils ne se corrigent pas au même endroit.
SETTING_STATUS_COLORS = {
    profile_translate.STATUS_MAPPED: "#1d4ed8",       # bleu : rejoué par le profil
    profile_translate.STATUS_UNSUPPORTED: "#111827",  # noir : à refaire dans Intella
    profile_translate.STATUS_UNKNOWN: "#b91c1c",      # rouge : nom inconnu, à vérifier
}


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
    win = tk.Toplevel(parent)
    win.title(titre or i18n.t("settings.title", "Réglages de la source"))
    win.geometry("940x600")
    win.transient(parent.winfo_toplevel())

    ttk.Label(win, wraplength=910, justify="left",
              font=("Segoe UI", 10, "bold"),
              text=i18n.t(
                  "settings.header",
                  "Un profil ne rejoue que les réglages qu'Intella accepte à "
                  "l'import automatique. Les autres sont à refaire à la main.")
              ).pack(anchor="w", padx=10, pady=(10, 2))
    ttk.Label(win, text=settings_summary(src)).pack(anchor="w", padx=10, pady=(0, 6))

    legende = ttk.Frame(win)
    legende.pack(fill="x", padx=10, pady=(0, 6))
    for etat in (profile_translate.STATUS_MAPPED,
                 profile_translate.STATUS_UNSUPPORTED,
                 profile_translate.STATUS_UNKNOWN):
        tk.Label(legende, text="■ " + setting_status_label(etat),
                 fg=SETTING_STATUS_COLORS[etat]).pack(side="left", padx=(0, 16))

    holder = ttk.Frame(win)
    holder.pack(fill="both", expand=True, padx=10, pady=(0, 10))
    tree = ttk.Treeview(holder, columns=("key", "label", "value", "state"),
                        show="headings")
    for col, entete, largeur in (
            ("key", i18n.t("settings.col_key", "Réglage (nom Intella)"), 230),
            ("label", i18n.t("settings.col_label", "Description"), 300),
            ("value", i18n.t("settings.col_value", "Valeur"), 150),
            ("state", i18n.t("settings.col_state", "État"), 190)):
        tree.heading(col, text=entete)
        tree.column(col, width=largeur, anchor="w")
    vsb = ttk.Scrollbar(holder, orient="vertical", command=tree.yview)
    tree.configure(yscrollcommand=vsb.set)
    tree.pack(side="left", fill="both", expand=True)
    vsb.pack(side="right", fill="y")
    for etat, couleur in SETTING_STATUS_COLORS.items():
        tree.tag_configure(etat, foreground=couleur)

    for ligne in profile_translate.describe_settings(src):
        etat = setting_status_label(ligne["status"])
        motif = setting_reason_label(ligne["reason"])
        if motif:
            etat += " — " + motif
        tree.insert("", "end", tags=(ligne["status"],),
                    values=(ligne["xml_key"], ligne["label"],
                            ligne["value"] or "—", etat))

    make_button(win, i18n.t("common.close", "Fermer"), win.destroy).pack(
        anchor="e", padx=10, pady=(0, 10))


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
