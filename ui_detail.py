"""Onglet « Détail du cas » : métadonnées humanisées du cas sélectionné.

Lit ``app.case_meta`` (rempli par l'onglet Inventaire dès qu'un ``case.xml`` est
détecté) et l'affiche en clair. Lecture seule, informatif.
"""

import tkinter as tk
from tkinter import ttk

import config
import i18n


class DetailTab(ttk.Frame):
    def __init__(self, parent, app):
        super().__init__(parent)
        self.app = app

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
        else:
            self.text.insert(
                "end",
                i18n.t("detail.no_tasks2", "Aucune tâche post-indexation déclarée.") + "\n",
                "muted")

        self.text.configure(state="disabled")

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
