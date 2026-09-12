"""Journal : opérations horodatées, filtrables par niveau, exportables.

Sous-onglet de **Maintenance** depuis le 09/09/2026.

**Pourquoi des filtres (décision D12, 11/09/2026).** Le journal mêle deux flux :
les lignes de l'application et la sortie brute d'IntellaCmd, qui débite des
centaines de lignes DEBUG par lecture de cas. L'avertissement qui compte — un
écart de cohérence des tailles, un sous-cas injoignable — s'y noyait, et le
compte des erreurs n'était visible qu'en relisant tout. Trois boutons et un
champ de recherche suffisent à le rendre consultable ; le compte remonte en
plus dans la barre d'état, visible depuis n'importe quel écran.
"""

import re
import tkinter as tk
from tkinter import filedialog, messagebox, ttk

import config
import i18n
import ui_theme
from ui_widgets import make_button

# Niveaux reconnus, du plus bas au plus haut. Les lignes d'IntellaCmd ne suivent
# pas le format de l'application (« [DEBUG] 2026-… », « INFO  stderr … ») : on
# cherche donc le mot-clé dans le DÉBUT de la ligne plutôt que par découpage
# positionnel, qui raterait un flux sur deux.
_NIVEAUX = ("DEBUG", "INFO", "WARN", "ERROR")
_RE_NIVEAU = re.compile(r"\b(DEBUG|INFO|WARNING|WARN|ERROR|ERREUR)\b")

# Filtres proposés.
F_ALL, F_ALERTS, F_ERRORS = "all", "alerts", "errors"

_COULEURS = {
    "DEBUG": config.UI_INK_3,
    "INFO": "#1d4ed8",
    "WARN": config.WARN_COLOR,
    "ERROR": config.DANGER_COLOR,
}


def level_of(ligne: str) -> str:
    """Niveau d'une ligne de journal, quelle que soit sa provenance."""
    m = _RE_NIVEAU.search(ligne[:48])
    if not m:
        return "INFO"
    mot = m.group(1)
    if mot in ("WARNING", "WARN"):
        return "WARN"
    if mot in ("ERROR", "ERREUR"):
        return "ERROR"
    return mot


class JournalTab(ttk.Frame):
    def __init__(self, parent, app):
        super().__init__(parent)
        self.app = app
        self._filtre = F_ALL
        self._recherche = ""
        self._counts = {n: 0 for n in _NIVEAUX}

        pad = app.theme.pad
        bar = ttk.Frame(self)
        bar.pack(fill="x", padx=pad, pady=(pad, 4))

        ttk.Label(bar, text=i18n.t("journal.search", "Rechercher") + " :").pack(side="left")
        self.var_query = tk.StringVar()
        entry = ttk.Entry(bar, textvariable=self.var_query, width=28)
        entry.pack(side="left", padx=(6, 10))
        entry.bind("<KeyRelease>", lambda _e: self._on_search())

        self.btn_all = make_button(bar, i18n.t("journal.filter_all", "Tout"),
                                   lambda: self._set_filter(F_ALL))
        self.btn_all.pack(side="left")
        self.btn_alerts = make_button(bar, "", lambda: self._set_filter(F_ALERTS),
                                      outline=config.WARN_COLOR)
        self.btn_alerts.pack(side="left", padx=4)
        self.btn_errors = make_button(bar, "", lambda: self._set_filter(F_ERRORS),
                                      outline=config.DANGER_COLOR)
        self.btn_errors.pack(side="left")

        make_button(bar, i18n.t("journal.clear", "Effacer"), self._clear).pack(side="right")
        make_button(bar, i18n.t("journal.export", "Exporter le journal…"),
                    self._export).pack(side="right", padx=6)

        holder = ttk.Frame(self)
        holder.pack(fill="both", expand=True, padx=pad, pady=(0, pad))
        self.text = tk.Text(holder, wrap="none", state="disabled",
                            background=config.UI_SURFACE, foreground=config.UI_INK,
                            font=ui_theme.F_MONO, relief="flat",
                            highlightthickness=1, highlightbackground=config.UI_LINE,
                            padx=8, pady=6)
        vsb = ttk.Scrollbar(holder, orient="vertical", command=self.text.yview)
        hsb = ttk.Scrollbar(holder, orient="horizontal", command=self.text.xview)
        self.text.configure(yscrollcommand=vsb.set, xscrollcommand=hsb.set)
        self.text.grid(row=0, column=0, sticky="nsew")
        vsb.grid(row=0, column=1, sticky="ns")
        hsb.grid(row=1, column=0, sticky="ew")
        holder.rowconfigure(0, weight=1)
        holder.columnconfigure(0, weight=1)
        for niveau, couleur in _COULEURS.items():
            self.text.tag_configure(niveau, foreground=couleur)

        self._refresh_buttons()
        self.app.log.add_listener(self._append)  # rejoue l'historique

    # ------------------------------------------------------------------ #
    # Réception — on travaille par LIGNE PHYSIQUE, pas par entrée         #
    # ------------------------------------------------------------------ #
    # 🐞 Corrigé le 11/09/2026. Une entrée de journal n'est pas une ligne : la
    # sortie brute d'IntellaCmd arrive en UN seul appel à `log()` et contient des
    # dizaines de retours à la ligne. Filtrer par entrée gardait donc le bloc
    # ENTIER dès qu'un mot s'y trouvait — 50 lignes affichées pour une seule qui
    # correspond, ce qui ressemble à une recherche qui ne filtre pas. Le défaut
    # ne se voyait pas avec le filtre « Alertes » : les entrées WARN, elles, sont
    # bien mono-ligne. Tout passe désormais par `_lignes()`.

    @staticmethod
    def _lignes(entree: str):
        """Découpe une entrée en (texte, niveau), une paire par ligne affichée.

        Une ligne de continuation (sans mot-clé de niveau) **hérite** du niveau
        de la précédente : sans cela, la suite d'un bloc d'erreur repasserait en
        bleu au milieu du message.
        """
        niveau = "INFO"
        for i, texte in enumerate((entree or "").splitlines() or [""]):
            trouve = _RE_NIVEAU.search(texte[:48])
            if trouve or i == 0:
                niveau = level_of(texte)
            yield texte, niveau

    def _append(self, entree: str):
        for texte, niveau in self._lignes(entree):
            self._counts[niveau] = self._counts.get(niveau, 0) + 1
            if self._garde(texte, niveau):
                self._write(texte, niveau)
        self._refresh_buttons()
        self._push_status()

    def _garde(self, ligne: str, niveau: str) -> bool:
        if self._filtre == F_ALERTS and niveau not in ("WARN", "ERROR"):
            return False
        if self._filtre == F_ERRORS and niveau != "ERROR":
            return False
        if self._recherche and self._recherche not in ligne.lower():
            return False
        return True

    def _write(self, ligne: str, niveau: str):
        self.text.configure(state="normal")
        self.text.insert("end", ligne + "\n", (niveau,))
        self.text.see("end")
        self.text.configure(state="disabled")

    # ------------------------------------------------------------------ #
    # Filtres                                                            #
    # ------------------------------------------------------------------ #
    def _set_filter(self, filtre):
        self._filtre = filtre
        self._rebuild()

    def _on_search(self):
        self._recherche = self.var_query.get().strip().lower()
        self._rebuild()

    def _rebuild(self):
        self.text.configure(state="normal")
        self.text.delete("1.0", "end")
        self.text.configure(state="disabled")
        self._counts = {n: 0 for n in _NIVEAUX}
        for entree in self.app.log.lines:
            for texte, niveau in self._lignes(entree):
                self._counts[niveau] = self._counts.get(niveau, 0) + 1
                if self._garde(texte, niveau):
                    self._write(texte, niveau)
        self._refresh_buttons()

    def _refresh_buttons(self):
        alertes = self._counts.get("WARN", 0)
        erreurs = self._counts.get("ERROR", 0)
        self.btn_alerts.configure(
            text=i18n.t("journal.filter_alerts", "Alertes") + f"  {alertes}")
        self.btn_errors.configure(
            text=i18n.t("journal.filter_errors", "Erreurs") + f"  {erreurs}")
        # Le filtre actif se voit : trois boutons identiques ne diraient pas
        # lequel est appliqué, et une liste filtrée passerait pour un journal vide.
        for filtre, bouton, couleur in (
                (F_ALL, self.btn_all, config.ACCENT),
                (F_ALERTS, self.btn_alerts, config.WARN_COLOR),
                (F_ERRORS, self.btn_errors, config.DANGER_COLOR)):
            actif = (self._filtre == filtre)
            bouton.configure(bg=couleur if actif else config.UI_SURFACE,
                             fg="white" if actif else couleur,
                             highlightbackground=couleur)

    def _push_status(self):
        """Remonte le compte dans la barre d'état : le journal n'est pas ouvert."""
        alertes = self._counts.get("WARN", 0)
        erreurs = self._counts.get("ERROR", 0)
        if not (alertes or erreurs) or not hasattr(self.app, "status"):
            return
        if erreurs:
            self.app.set_status(i18n.t(
                "journal.status_errors", "{e} erreur(s) et {a} alerte(s) — voir le journal",
                e=erreurs, a=alertes), "error")
        else:
            self.app.set_status(i18n.t(
                "journal.status_alerts", "{a} alerte(s) — voir le journal", a=alertes),
                "warn")

    # ------------------------------------------------------------------ #
    def _clear(self):
        self.app.log.clear()
        self._counts = {n: 0 for n in _NIVEAUX}
        self._rebuild()
        self.app.log.log(i18n.t("journal.cleared", "Journal effacé."))

    def _export(self):
        default = f"journal_{config.now_compact()}.log"
        path = filedialog.asksaveasfilename(
            defaultextension=".log", initialfile=default,
            filetypes=[(i18n.t("journal.filetype_log", "Journal"), "*.log"),
                       (i18n.t("common.filetype_text", "Texte"), "*.txt"),
                       (i18n.t("common.filetype_all", "Tous"), "*.*")],
        )
        if not path:
            return
        try:
            self.app.log.export(path)
            self.app.log.log(i18n.t("journal.exported_log", "Journal exporté : {p}", p=path))
            messagebox.showinfo(i18n.t("tabs.journal", "Journal"),
                                i18n.t("journal.exported_msg", "Journal exporté :\n{p}", p=path))
        except OSError as exc:
            messagebox.showerror(i18n.t("tabs.journal", "Journal"),
                                 i18n.t("journal.export_failed", "Échec de l'export :\n{e}", e=exc))
