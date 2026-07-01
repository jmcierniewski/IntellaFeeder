"""Onglet Journal : affiche les opérations horodatées, export possible."""

import tkinter as tk
from tkinter import filedialog, messagebox, ttk

import config
import i18n
from ui_widgets import make_button


class JournalTab(ttk.Frame):
    def __init__(self, parent, app):
        super().__init__(parent)
        self.app = app

        bar = ttk.Frame(self)
        bar.pack(fill="x", padx=8, pady=6)
        make_button(bar, i18n.t("journal.export", "Exporter le journal…"), self._export).pack(side="left")
        make_button(bar, i18n.t("journal.clear", "Effacer"), self._clear).pack(side="left", padx=6)

        holder = ttk.Frame(self)
        holder.pack(fill="both", expand=True, padx=8, pady=(0, 8))
        self.text = tk.Text(holder, wrap="word", state="disabled", height=20)
        vsb = ttk.Scrollbar(holder, orient="vertical", command=self.text.yview)
        self.text.configure(yscrollcommand=vsb.set)
        self.text.pack(side="left", fill="both", expand=True)
        vsb.pack(side="right", fill="y")

        self.app.log.add_listener(self._append)  # rejoue l'historique

    def _append(self, line: str):
        self.text.configure(state="normal")
        self.text.insert("end", line + "\n")
        self.text.see("end")
        self.text.configure(state="disabled")

    def _clear(self):
        self.app.log.clear()
        self.text.configure(state="normal")
        self.text.delete("1.0", "end")
        self.text.configure(state="disabled")
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
