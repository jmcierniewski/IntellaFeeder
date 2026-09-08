"""Onglet « Détail du cas » : métadonnées humanisées du cas sélectionné.

Lit ``app.case_meta`` (rempli par l'onglet Inventaire dès qu'un ``case.xml`` est
détecté) et l'affiche en clair. Lecture seule, informatif.

Cas **compound** : une section « Sous-cas référencés », placée juste après
l'identité du cas, donne pour chacun nom, taille, chemin, accessibilité et
**utilisateurs autorisés** (les droits sont portés par le sous-cas, pas par le
compound) — c'est ici, avec l'Inventaire, que se lit un compound, l'Import lui
étant fermé.
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
    # Abscisse (px) de la colonne des valeurs — cf. `tabs` plus bas.
    LABEL_COL = 250

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

        # Valeurs alignées sur une colonne fixe : un « clé : valeur » libre
        # redémarre à une abscisse différente à chaque ligne, ce qui donne le
        # sentiment de fouillis même quand le contenu est court. Le 2e taquet
        # évite qu'un libellé plus large que la colonne ne colle sa valeur.
        self.text.configure(tabs=(self.LABEL_COL, self.LABEL_COL + 16))
        self.text.tag_configure("h1", font=("Segoe UI", 12, "bold"),
                                foreground="#1e40af", spacing1=16, spacing3=8)
        self.text.tag_configure("k", font=("Segoe UI", 10, "bold"),
                                lmargin1=8, lmargin2=8)
        self.text.tag_configure("v", font=("Segoe UI", 10), lmargin1=8,
                                lmargin2=self.LABEL_COL, spacing3=2)
        self.text.tag_configure("muted", font=("Segoe UI", 9, "italic"),
                                foreground="#64748b", lmargin1=8, lmargin2=8,
                                spacing1=4)
        # Sous-cas : un bloc par cas référencé (titre puis lignes de détail).
        self.text.tag_configure("sub", font=("Segoe UI", 10, "bold"),
                                lmargin1=16, lmargin2=36, spacing1=6)
        self.text.tag_configure("sub_ko", font=("Segoe UI", 10, "bold"),
                                foreground="#b91c1c", lmargin1=16, lmargin2=36,
                                spacing1=6)
        self.text.tag_configure("sub_kv", font=("Segoe UI", 9), foreground="#334155",
                                lmargin1=36, lmargin2=36)
        self.text.tag_configure("sub_path", font=("Segoe UI", 9), foreground="#64748b",
                                lmargin1=36, lmargin2=36)
        self.text.tag_configure("bullet", font=("Segoe UI", 10),
                                lmargin1=16, lmargin2=32)
        # Nom du cas : c'est LA donnée qu'on vient vérifier en ouvrant l'onglet.
        self.text.tag_configure("v_strong", font=("Segoe UI", 11, "bold"),
                                lmargin1=8, lmargin2=self.LABEL_COL)
        self.text.tag_configure("warn", font=("Segoe UI", 9, "bold"),
                                foreground="#b45309", lmargin1=8, lmargin2=8,
                                spacing1=4)

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
        self._kv(i18n.t("detail.name", "Nom"), xml["name"], tag="v_strong")
        self._kv(i18n.t("detail.folder", "Dossier"), meta["folder"])
        if meta.get("is_compound"):
            self._kv(i18n.t("detail.kind", "Type de cas"), i18n.t(
                "detail.kind_compound",
                "COMPOUND — référence {c} sous-cas, aucune source en propre "
                "(import impossible ; visez un sous-cas)", c=len(meta.get("subcases", []))))
        if xml["description"]:
            self._kv(i18n.t("detail.description", "Description"), xml["description"])
        self._kv(i18n.t("detail.id", "Identifiant"), xml["id"])
        self._kv(i18n.t("detail.created", "Créé le"), config.epoch_ms_to_str(xml["timestamp"]))
        self._kv(i18n.t("detail.last_opened", "Dernière ouverture"),
                 config.epoch_ms_to_str(xml["lastOpened"]))
        self._kv(i18n.t("detail.created_by", "Créé par"), xml["user"])
        self._kv(i18n.t("detail.size_total", "Taille totale (tous sous-cas)")
                 if meta.get("is_compound") else i18n.t("detail.size", "Taille occupée"),
                 i18n.t("detail.size_value", "{h}  ({b:,} octets)",
                        h=config.human_size(xml["size"]), b=xml["size"]))
        self._kv(i18n.t("detail.version", "Version (origine / actuelle)"),
                 f"{xml['originalVersion'] or '—'} / {xml['caseVersion'] or '—'}")

        # Compound : les sous-cas AVANT les préférences — c'est l'information
        # structurante du cas, et elle porte maintenant les droits de chacun.
        if meta.get("is_compound"):
            self._subcases_section(meta)

        self._h1(i18n.t("detail.h1_prefs", "Préférences du cas"))
        opt = prefs.get("OptimizationFolderPath", "")
        self._kv(i18n.t("detail.optim_folder", "Dossier d'optimisation"), opt or "—")
        # Utilisateurs autorisés du cas lui-même. Pour un compound, ceux des
        # sous-cas sont donnés sous-cas par sous-cas (section ci-dessus) plutôt
        # qu'en une ligne consolidée : c'est le détail qui sert à savoir qui
        # ouvrira quoi, la liste fusionnée ne disait rien d'actionnable.
        users = list(meta.get("authorized_users", []))
        if users:
            self._kv(i18n.t("detail.authorized_users", "Utilisateurs autorisés"),
                     ", ".join(users))
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
                self.text.insert("end", "•  " + name + "\n", "bullet")
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

    def _subcases_section(self, meta):
        """Liste les sous-cas : nom, taille, chemin, droits, accessibilité.

        Un sous-cas peut être déclaré sans être joignable depuis ce poste (chemin
        absolu vers un partage démonté, compound recopié sans ses sous-cas) : on
        l'affiche quand même, marqué, car sa seule déclaration est une
        information — et son absence explique un inventaire incomplet.
        """
        subs = meta.get("subcases", [])
        self._h1(i18n.t("detail.h1_subcases", "Sous-cas référencés"))
        if not subs:
            self.text.insert("end", i18n.t(
                "detail.no_subcase",
                "Cas déclaré compound mais ne référençant aucun sous-cas.") + "\n", "muted")
            return
        known = sum(sc["size"] for sc in subs if sc["exists"])
        users_label = i18n.t("detail.authorized_users", "Utilisateurs autorisés")
        optim_label = i18n.t("detail.optim_folder", "Dossier d'optimisation")
        for num, sc in enumerate(subs, 1):
            if sc["exists"]:
                line = i18n.t("detail.subcase_ok", "{n} — {s}",
                              n=sc["name"], s=config.human_size(sc["size"]))
                self.text.insert("end", f"{num}.  " + line + "\n", "sub")
            else:
                line = i18n.t("detail.subcase_ko", "{n} — non joignable : {e}",
                              n=sc["name"], e=sc["error"])
                self.text.insert("end", f"{num}.  ✕ " + line + "\n", "sub_ko")
            self.text.insert("end", sc["path"] + "\n", "sub_path")
            # Droits et dossier d'optimisation PAR SOUS-CAS : c'est le sous-cas
            # qui les porte, et deux sous-cas d'un même lot ne s'accordent pas
            # forcément — ni sur les personnes, ni sur l'emplacement.
            if sc["exists"]:
                self.text.insert(
                    "end",
                    users_label + " : " + (", ".join(sc.get("authorized_users", [])) or "—")
                    + "\n", "sub_kv")
                self.text.insert(
                    "end", optim_label + " : " + (sc.get("optimization") or "—") + "\n",
                    "sub_kv")
        self._optimization_warning(meta, subs)
        self._users_warning(subs)
        missing = [sc for sc in subs if not sc["exists"]]
        recap = i18n.t(
            "detail.subcases_recap",
            "{t} sous-cas — {k} lisible(s) totalisant {b} ; la taille du compound "
            "ci-dessus ({c}) fait foi.",
            t=len(subs), k=len(subs) - len(missing), b=config.human_size(known),
            c=config.human_size(meta["size"]))
        if missing:
            recap += " " + i18n.t(
                "detail.subcases_recap_missing",
                "{n} sous-cas non joignable(s) : l'inventaire des sources sera partiel.",
                n=len(missing))
        self.text.insert("end", recap + "\n", "muted")

    def _optimization_warning(self, meta, subs):
        """Alerte si les cas du lot ne pointent pas au même dossier d'optimisation.

        Un seul dossier par cas, mais rien n'oblige deux sous-cas à partager le
        même : l'écart se paie en performances d'indexation, et il ne se voit
        nulle part ailleurs qu'ici. Les sous-cas non joignables sont exclus de
        la comparaison — on ne sait pas ce qu'ils déclarent.
        """
        # Regroupement insensible à la casse, mais AFFICHAGE de la graphie
        # d'origine : un chemin rendu en minuscules se relit mal et ne
        # correspond plus à ce qui est écrit dans le case.prefs.
        valeurs = {}
        for nom, opt in ([(meta.get("name", ""), meta.get("optimization", ""))]
                         + [(sc["name"], sc.get("optimization", ""))
                            for sc in subs if sc["exists"]]):
            opt = (opt or "").strip()
            cle = opt.lower()
            valeurs.setdefault(cle, (opt, []))[1].append(nom)
        if len(valeurs) < 2:
            return
        detail = " / ".join(f"« {opt or '—'} » : {', '.join(noms)}"
                            for opt, noms in valeurs.values())
        self.text.insert("end", i18n.t(
            "detail.optim_diverge",
            "⚠ Dossiers d'optimisation différents dans ce lot — {d}", d=detail) + "\n",
            "warn")

    def _users_warning(self, subs):
        """Alerte si les sous-cas n'ouvrent pas aux mêmes personnes.

        Volontairement BRÈVE (demande du 07/09/2026) : la liste de chacun est
        déjà donnée sous son bloc, on ne redit ici que les noms qui manquent
        quelque part — c'est la seule information qui ne se lit pas d'un coup
        d'œil quand il y a plusieurs sous-cas.
        """
        lisibles = [sc for sc in subs if sc["exists"]]
        if len(lisibles) < 2:
            return
        listes = [set(sc.get("authorized_users", [])) for sc in lisibles]
        partout = set.intersection(*listes)
        partiels = sorted(set.union(*listes) - partout)
        if not partiels:
            return
        self.text.insert("end", i18n.t(
            "detail.users_diverge",
            "⚠ Droits inégaux entre sous-cas — pas partout : {u}",
            u=", ".join(partiels)) + "\n", "warn")

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

    def _kv(self, key, value, tag: str = "v"):
        self.text.insert("end", key + " :\t", "k")
        self.text.insert("end", str(value) + "\n", tag)


def _yesno(raw) -> str:
    if raw is None:
        return "—"
    return i18n.t("common.yes", "oui") if str(raw).strip().lower() == "true" \
        else i18n.t("common.no", "non")
