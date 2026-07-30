"""Onglet « Détail du cas » : métadonnées humanisées du cas sélectionné.

Lit ``app.case_meta`` (rempli par l'onglet Inventaire dès qu'un ``case.xml`` est
détecté) et l'affiche en clair. Lecture seule, informatif.
"""

import os
import shutil
import tkinter as tk
from tkinter import filedialog, messagebox, ttk

import case_meta
import config
import i18n
from ui_widgets import make_button


class DetailTab(ttk.Frame):
    def __init__(self, parent, app):
        super().__init__(parent)
        self.app = app

        # Barre d'action : export de tasks2.json comme fichier de tâches.
        actions = ttk.Frame(self)
        actions.pack(fill="x", padx=12, pady=(8, 0))
        self.btn_export_tasks2 = make_button(
            actions, i18n.t("detail.export_tasks2", "Exporter ces tâches (fichier de tâches)…"),
            self._export_tasks2)
        self.btn_export_tasks2.pack(side="left")

        holder = ttk.Frame(self)
        holder.pack(fill="both", expand=True, padx=8, pady=8)
        self.text = tk.Text(holder, wrap="word", state="disabled", padx=10, pady=10,
                            relief="flat", cursor="arrow")
        vsb = ttk.Scrollbar(holder, orient="vertical", command=self.text.yview)
        self.text.configure(yscrollcommand=vsb.set)
        self.text.pack(side="left", fill="both", expand=True)
        vsb.pack(side="right", fill="y")

        self.text.tag_configure("h1", font=("Segoe UI", 13, "bold"),
                                foreground="#1e40af", spacing1=12, spacing3=6)
        self.text.tag_configure("k", font=("Segoe UI", 10, "bold"),
                                lmargin1=8, lmargin2=8)
        self.text.tag_configure("v", font=("Segoe UI", 10), lmargin1=8, lmargin2=180)
        self.text.tag_configure("muted", font=("Segoe UI", 10, "italic"),
                                foreground="#64748b")

        self.refresh()

    # ------------------------------------------------------------------ #
    def refresh(self):
        meta = self.app.case_meta
        self.text.configure(state="normal")
        self.text.delete("1.0", "end")
        self.btn_export_tasks2.configure(state="disabled")
        if not meta:
            self.text.insert(
                "end",
                i18n.t("detail.no_case",
                       "Sélectionnez un cas dans l'onglet « 1. Inventaire du cas ».") + "\n",
                "muted")
            self.text.configure(state="disabled")
            return

        xml = meta["xml"]
        prefs = meta.get("prefs", {})

        self._h1(i18n.t("detail.h1_case", "Cas"))
        self._kv(i18n.t("detail.name", "Nom"), xml["name"])
        self._kv(i18n.t("detail.folder", "Dossier"), meta["folder"])
        if xml["description"]:
            self._kv(i18n.t("detail.description", "Description"), xml["description"])
        self._kv(i18n.t("detail.id", "Identifiant"), xml["id"])
        self._kv(i18n.t("detail.created", "Créé le"), config.epoch_ms_to_str(xml["timestamp"]))
        self._kv(i18n.t("detail.last_opened", "Dernière ouverture"),
                 config.epoch_ms_to_str(xml["lastOpened"]))
        self._kv(i18n.t("detail.created_by", "Créé par"), xml["user"])
        self._kv(i18n.t("detail.size", "Taille occupée"),
                 i18n.t("detail.size_value", "{h}  ({b:,} octets)",
                        h=config.human_size(xml["size"]), b=xml["size"]))
        self._kv(i18n.t("detail.version", "Version (origine / actuelle)"),
                 f"{xml['originalVersion'] or '—'} / {xml['caseVersion'] or '—'}")

        self._h1(i18n.t("detail.h1_prefs", "Préférences du cas"))
        opt = prefs.get("OptimizationFolderPath", "")
        self._kv(i18n.t("detail.optim_folder", "Dossier d'optimisation"), opt or "—")
        users = prefs.get("InitialAuthorizedUsers", "")
        if users:
            self._kv(i18n.t("detail.authorized_users", "Utilisateurs autorisés"),
                     ", ".join(u for u in users.split(",") if u))
        self._kv(i18n.t("detail.email_threading", "Email Threading effectué"),
                 _yesno(prefs.get("TasksEmailThreadsAnalysisDone")))
        self._kv(i18n.t("detail.saved_searches", "Recherches enregistrées effectuées"),
                 _yesno(prefs.get("TasksSavedSearchDone")))
        algo = prefs.get("MessageHashingAlgorithm")
        if algo:
            self._kv(i18n.t("detail.hash_algo", "Hachage des messages"), algo)

        tasks2 = meta.get("tasks2", [])
        self._h1(i18n.t("detail.h1_tasks2", "Tâches post-indexation (tasks2.json)"))
        if tasks2:
            for name in tasks2:
                self.text.insert("end", "•  " + name + "\n", "v")
            # Le fichier est un tableau JSON de tâches : réutilisable tel quel
            # comme « fichier de tâches » de l'onglet Import (après export).
            self.text.insert(
                "end",
                i18n.t("detail.tasks2_hint",
                       "Ces tâches peuvent être exportées (bouton en haut) puis désignées "
                       "comme « fichier de tâches » dans l'onglet « Import » : elles seront "
                       "alors exécutées pendant l'import, source par source.") + "\n",
                "muted")
            if os.path.isfile(case_meta.tasks2_path(meta["folder"])):
                self.btn_export_tasks2.configure(state="normal")
        else:
            self.text.insert(
                "end",
                i18n.t("detail.no_tasks2", "Aucune tâche post-indexation déclarée.") + "\n",
                "muted")

        self.text.configure(state="disabled")

    # ------------------------------------------------------------------ #
    def _export_tasks2(self):
        """Copie ``prefs\\tasks2.json`` où l'utilisateur veut.

        Copie **verbatim** (pas de re-sérialisation) : le fichier est déjà un
        tableau JSON de tâches au format attendu par ``task_builder.load_tasks``,
        donc directement désignable comme « fichier de tâches » à l'Import.
        """
        title = i18n.t("detail.export_tasks2_title", "Exporter les tâches post-indexation")
        meta = self.app.case_meta
        src = case_meta.tasks2_path(meta["folder"]) if meta else ""
        if not src or not os.path.isfile(src):
            messagebox.showinfo(title, i18n.t(
                "detail.export_tasks2_none",
                "Ce cas ne déclare aucune tâche post-indexation (tasks2.json absent)."))
            return
        safe = config.sanitize_filename(meta["name"] or "Case")
        path = filedialog.asksaveasfilename(
            defaultextension=".json", initialfile=f"tasks2_{safe}.json",
            filetypes=[("JSON", "*.json"), (i18n.t("common.filetype_all", "Tous"), "*.*")])
        if not path:
            return
        try:
            shutil.copyfile(src, path)
            self.app.log.log(i18n.t(
                "detail.export_tasks2_log", "Tâches post-indexation exportées : {p}", p=path))
            messagebox.showinfo(title, i18n.t(
                "detail.export_tasks2_msg",
                "Tâches exportées :\n{p}\n\nDésignez ce fichier comme « fichier de tâches » "
                "dans l'onglet « Import » pour les exécuter pendant l'indexation.", p=path))
        except OSError as exc:
            messagebox.showerror(title, i18n.t("common.export_failed", "Échec :\n{e}", e=exc))

    def _h1(self, title):
        self.text.insert("end", title + "\n", "h1")

    def _kv(self, key, value):
        self.text.insert("end", key + " : ", "k")
        self.text.insert("end", str(value) + "\n", "v")


def _yesno(raw) -> str:
    if raw is None:
        return "—"
    return i18n.t("common.yes", "oui") if str(raw).strip().lower() == "true" \
        else i18n.t("common.no", "non")
