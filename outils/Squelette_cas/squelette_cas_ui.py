"""Petite interface graphique pour ``squelette_cas.py``.

Un écran, deux champs, un bouton. L'outil en ligne de commande reste la
référence ; cette fenêtre évite d'avoir à retenir les options quand on fabrique
un banc d'essai depuis un poste, et elle rend visibles les deux choses qu'un
oubli rend coûteuses : le **mode brut** (le dossier produit contient alors des
données réelles) et le **verdict d'anonymat**.

    python squelette_cas_ui.py [dossier du cas] [dossier de sortie]

Les noms de cas du squelette portent un **GDH** (groupe date-heure) commun à
toute la fabrication : ``CAS_CP_<gdh>`` pour un compound, ``CAS_CP_<n>_<gdh>``
pour ses sous-cas, ``CAS_<gdh>`` pour un cas simple. Il est rappelé dans le
compte rendu et le manifeste.

Les contrôles ne sont pas réimplémentés ici : la fenêtre passe par
``squelette_cas.valider`` puis ``squelette_cas.fabriquer``, exactement comme le
CLI. Une interface qui referait ses propres tests finirait par en desserrer un.

Autonome comme le script qu'elle pilote : bibliothèque standard seule, aucun
import d'IntellaFeeder. Le travail tourne dans un **thread** (un parcours réseau
peut durer) qui ne touche aucun widget : il poste dans une file drainée par la
boucle Tk — même contrat que le reste du projet.
"""

from __future__ import annotations

import os
import queue
import subprocess
import sys
import threading
import tkinter as tk
from tkinter import filedialog, messagebox, ttk

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import squelette_cas as sq

ROUGE = "#b91c1c"
VERT = "#15803d"
GRIS = "#64748b"


class SqueletteUI:
    def __init__(self, root: tk.Tk, cas: str = "", sortie: str = ""):
        self.root = root
        self.file: queue.Queue = queue.Queue()
        self.en_cours = False
        self.dernier_dossier = ""

        root.title("Squelette de cas — banc d'essai IntellaFeeder")
        root.geometry("880x620")
        root.minsize(760, 560)

        self.var_cas = tk.StringVar(value=cas)
        self.var_sortie = tk.StringVar(value=sortie)
        self.var_brut = tk.BooleanVar(value=False)
        self.var_logs = tk.StringVar(value="inventaire")
        self.var_nb_logs = tk.StringVar(value="5")
        self.var_max_ko = tk.StringVar(value="256")
        self.var_force = tk.BooleanVar(value=False)

        self._construire()
        self._sur_changement_mode()

    # ------------------------------------------------------------------ #
    def _construire(self):
        cadre = ttk.LabelFrame(self.root, text="Cas source et destination")
        cadre.pack(fill="x", padx=10, pady=(10, 6))
        cadre.columnconfigure(1, weight=1)

        ttk.Label(cadre, text="Dossier du cas").grid(row=0, column=0, sticky="w",
                                                     padx=6, pady=5)
        ttk.Entry(cadre, textvariable=self.var_cas).grid(row=0, column=1, sticky="ew",
                                                         padx=6, pady=5)
        ttk.Button(cadre, text="Parcourir…", command=self._choisir_cas).grid(
            row=0, column=2, padx=6, pady=5)

        ttk.Label(cadre, text="Dossier de sortie").grid(row=1, column=0, sticky="w",
                                                        padx=6, pady=5)
        ttk.Entry(cadre, textvariable=self.var_sortie).grid(row=1, column=1, sticky="ew",
                                                            padx=6, pady=5)
        ttk.Button(cadre, text="Parcourir…", command=self._choisir_sortie).grid(
            row=1, column=2, padx=6, pady=5)

        self.lbl_cas = ttk.Label(cadre, text="", foreground=GRIS)
        self.lbl_cas.grid(row=2, column=1, columnspan=2, sticky="w", padx=6, pady=(0, 6))

        # ------------------------------------------------------------------
        opts = ttk.LabelFrame(self.root, text="Options")
        opts.pack(fill="x", padx=10, pady=6)
        opts.columnconfigure(3, weight=1)

        ttk.Checkbutton(opts, text="Mode BRUT — copier sans anonymiser",
                        variable=self.var_brut,
                        command=self._sur_changement_mode).grid(
            row=0, column=0, columnspan=2, sticky="w", padx=6, pady=(6, 0))
        # L'avertissement occupe une ligne permanente : il apparait a la seconde
        # ou la case est cochee, la ou une popup au lancement arriverait apres
        # que l'utilisateur a cesse d'y penser.
        self.lbl_mode = ttk.Label(opts, text="", wraplength=820, justify="left")
        self.lbl_mode.grid(row=1, column=0, columnspan=4, sticky="w", padx=26, pady=(2, 8))

        ttk.Label(opts, text="Logs").grid(row=2, column=0, sticky="w", padx=6, pady=5)
        cb = ttk.Combobox(opts, textvariable=self.var_logs, state="readonly", width=12,
                          values=("aucun", "inventaire", "brut"))
        cb.grid(row=2, column=1, sticky="w", padx=6, pady=5)
        cb.bind("<<ComboboxSelected>>", lambda _e: self._sur_changement_mode())

        ttk.Label(opts, text="Nombre").grid(row=2, column=2, sticky="e", padx=(20, 4))
        ttk.Spinbox(opts, from_=1, to=200, width=5,
                    textvariable=self.var_nb_logs).grid(row=2, column=3, sticky="w")

        ttk.Label(opts, text="Troncature (Ko)").grid(row=3, column=2, sticky="e",
                                                     padx=(20, 4), pady=(0, 6))
        self.spin_ko = ttk.Spinbox(opts, from_=1, to=100_000, width=7,
                                   textvariable=self.var_max_ko)
        self.spin_ko.grid(row=3, column=3, sticky="w", pady=(0, 6))

        ttk.Checkbutton(opts, text="Écraser le dossier de sortie s'il n'est pas vide",
                        variable=self.var_force).grid(row=3, column=0, columnspan=2,
                                                      sticky="w", padx=6, pady=(0, 6))

        # ------------------------------------------------------------------
        barre = ttk.Frame(self.root)
        barre.pack(fill="x", padx=10, pady=(0, 6))
        self.btn_go = ttk.Button(barre, text="Fabriquer le squelette",
                                 command=self._lancer)
        self.btn_go.pack(side="left")
        self.btn_ouvrir = ttk.Button(barre, text="Ouvrir le dossier",
                                     command=self._ouvrir_dossier, state="disabled")
        self.btn_ouvrir.pack(side="left", padx=6)
        self.progress = ttk.Progressbar(barre, mode="indeterminate", length=180)
        self.lbl_etat = ttk.Label(barre, text="", foreground=GRIS)
        self.lbl_etat.pack(side="right")

        # ------------------------------------------------------------------
        sortie = ttk.LabelFrame(self.root, text="Compte rendu")
        sortie.pack(fill="both", expand=True, padx=10, pady=(0, 10))
        self.txt = tk.Text(sortie, wrap="word", state="disabled", relief="flat",
                           padx=8, pady=8, font=("Consolas", 9))
        vsb = ttk.Scrollbar(sortie, orient="vertical", command=self.txt.yview)
        self.txt.configure(yscrollcommand=vsb.set)
        self.txt.pack(side="left", fill="both", expand=True)
        vsb.pack(side="right", fill="y")
        self.txt.tag_configure("ok", foreground=VERT)
        self.txt.tag_configure("ko", foreground=ROUGE)
        self.txt.tag_configure("gris", foreground=GRIS)
        self.txt.tag_configure("gras", font=("Consolas", 9, "bold"))

        self._ecrire("Choisissez un dossier de cas Intella (compound ou simple), "
                     "puis « Fabriquer le squelette ».\n", "gris")

    # ------------------------------------------------------------------ #
    def _sur_changement_mode(self):
        """Reflète le mode choisi : l'avertissement doit précéder le clic."""
        brut = self.var_brut.get()
        if brut:
            self.lbl_mode.configure(
                foreground=ROUGE,
                text="⚠ Le dossier produit contiendra des DONNÉES RÉELLES (noms de "
                     "cas, utilisateurs, chemins). À traiter comme le cas d'origine : "
                     "hors ZONE DE LECTURE LIBRE, ne pas diffuser.")
        else:
            self.lbl_mode.configure(
                foreground=VERT,
                text="✓ Anonymisé : noms, utilisateurs et chemins remplacés ; tailles, "
                     "fuseaux, options d'indexation et forme des chemins conservés. "
                     "Le résultat est lisible et diffusable.")
        # « Troncature » ne veut rien dire tant que les logs ne sont pas copiés.
        self.spin_ko.configure(state="normal" if self.var_logs.get() == "brut"
                               else "disabled")

    def _choisir_cas(self):
        courant = self.var_cas.get().strip()
        d = filedialog.askdirectory(
            title="Dossier du cas Intella",
            initialdir=courant if os.path.isdir(courant) else None)
        if not d:
            return
        self.var_cas.set(os.path.normpath(d))
        self._decrire_cas()
        # Proposition de sortie seulement si le champ est vide : ne jamais
        # remplacer un choix deja fait par l'utilisateur.
        if not self.var_sortie.get().strip():
            parent = os.path.dirname(os.path.normpath(d))
            self.var_sortie.set(os.path.join(parent, "squelette_test"))

    def _choisir_sortie(self):
        courant = self.var_sortie.get().strip()
        d = filedialog.askdirectory(
            title="Dossier de sortie",
            initialdir=courant if os.path.isdir(courant) else None)
        if d:
            self.var_sortie.set(os.path.normpath(d))

    def _decrire_cas(self):
        """Dit tout de suite ce qu'est le dossier choisi : compound ou simple.

        L'information vient du seul ``case.xml`` — aucune lecture de données, et
        elle évite de lancer une fabrication sur un dossier qui n'est pas un cas.
        """
        chemin = self.var_cas.get().strip()
        if not chemin or not os.path.isfile(os.path.join(chemin, sq.CASE_XML)):
            self.lbl_cas.configure(text="Pas un dossier de cas Intella (case.xml absent).",
                                   foreground=ROUGE)
            return
        try:
            import xml.etree.ElementTree as ET
            racine = ET.parse(os.path.join(chemin, sq.CASE_XML)).getroot()
        except Exception as exc:  # noqa: BLE001 — XML illisible : on le dit, c'est tout
            self.lbl_cas.configure(text="case.xml illisible : {}".format(exc),
                                   foreground=ROUGE)
            return
        compound = (racine.get("compound", "") or "").strip().lower() == "true"
        bloc = racine.find("subcases")
        nb = len(bloc.findall("subcase")) if bloc is not None else 0
        if compound:
            texte = "Cas COMPOUND — {} sous-cas référencé(s) ; ceux qui sont " \
                    "joignables seront copiés aussi.".format(nb)
        else:
            texte = "Cas simple (pas de sous-cas)."
        self.lbl_cas.configure(text=texte, foreground=GRIS)

    # ------------------------------------------------------------------ #
    def _options(self):
        def entier(var, defaut):
            try:
                return max(1, int(var.get()))
            except (TypeError, ValueError):
                return defaut
        return sq.Options(
            cas=self.var_cas.get().strip().strip('"').strip("'"),
            sortie=self.var_sortie.get().strip().strip('"').strip("'"),
            brut=self.var_brut.get(),
            logs=self.var_logs.get(),
            nb_logs=entier(self.var_nb_logs, 5),
            max_log_ko=entier(self.var_max_ko, 256),
            force=self.var_force.get(),
        )

    def _lancer(self):
        if self.en_cours:
            return
        options = self._options()
        refus = sq.valider(options)
        if refus:
            complement = ""
            if refus.startswith("Dossier de sortie non vide"):
                complement = "\n\nCochez « Écraser le dossier de sortie » pour passer outre."
            messagebox.showwarning("Fabrication impossible", refus + complement)
            return
        if options.brut and not messagebox.askyesno(
                "Mode brut",
                "Le squelette contiendra des données réelles : noms de cas, "
                "utilisateurs, chemins" +
                (", et le contenu des logs copiés" if options.logs == "brut" else "") +
                ".\n\nIl sera hors ZONE DE LECTURE LIBRE et ne devra pas être "
                "diffusé.\n\nContinuer ?"):
            return

        self.en_cours = True
        self.btn_go.configure(state="disabled")
        self.btn_ouvrir.configure(state="disabled")
        self.progress.pack(side="left", padx=10)
        self.progress.start(12)
        self.lbl_etat.configure(text="Fabrication en cours…")
        self._vider()
        self._ecrire("Lecture de {}\n\n".format(options.cas), "gris")
        threading.Thread(target=self._worker, args=(options,), daemon=True).start()
        self.root.after(100, self._drainer)

    def _worker(self, options):
        """Thread : ne touche aucun widget, poste son résultat dans la file."""
        try:
            rapport, fuites = sq.fabriquer(options)
            self.file.put(("fini", options, rapport, fuites))
        except Exception as exc:  # noqa: BLE001 — remonté tel quel dans la fenêtre
            self.file.put(("erreur", options, exc, None))

    def _drainer(self):
        try:
            etat, options, a, b = self.file.get_nowait()
        except queue.Empty:
            self.root.after(100, self._drainer)
            return
        self.en_cours = False
        self.progress.stop()
        self.progress.pack_forget()
        self.btn_go.configure(state="normal")
        if etat == "erreur":
            self.lbl_etat.configure(text="Échec", foreground=ROUGE)
            self._ecrire("Échec : {}\n".format(a), "ko")
            messagebox.showerror("Échec", str(a))
            return
        self._afficher(options, a, b)

    # ------------------------------------------------------------------ #
    def _afficher(self, options, rapport, fuites):
        self.dernier_dossier = os.path.abspath(options.sortie)
        self.btn_ouvrir.configure(state="normal")
        for ligne in sq._lignes_rapport(rapport):
            self._ecrire(ligne + "\n", "ko" if "[X]" in ligne else None)
        if rapport.get("gdh"):
            # Le GDH est dans tous les noms de cas : l'afficher evite d'aller le
            # relire dans le manifeste pour retrouver la fabrication.
            self._ecrire("\nGDH des noms de cas : {}\n".format(rapport["gdh"]), "gris")
        self._ecrire("\nÉcrit dans : {}\n".format(self.dernier_dossier), "gras")
        self._ecrire("Manifeste : {}\n\n".format(
            os.path.join(self.dernier_dossier, sq.MANIFESTE)), "gris")

        if options.brut:
            self.lbl_etat.configure(text="Terminé (mode brut)", foreground=ROUGE)
            self._ecrire("⚠ Mode brut : ce dossier contient des données réelles. "
                         "Hors ZONE DE LECTURE LIBRE.\n", "ko")
            return
        if fuites:
            self.lbl_etat.configure(text="Anonymat NON garanti", foreground=ROUGE)
            self._ecrire("✕ {} valeur(s) d'origine retrouvée(s) dans le "
                         "squelette :\n".format(len(fuites)), "ko")
            for f in fuites:
                self._ecrire("    {}\n".format(f), "ko")
            self._ecrire("\nNe pas diffuser ce dossier en l'état.\n", "ko")
            messagebox.showwarning(
                "Anonymat non garanti",
                "{} valeur(s) d'origine subsistent dans le squelette.\n\n"
                "Le détail est dans le compte rendu et dans le manifeste."
                .format(len(fuites)))
            return
        self.lbl_etat.configure(text="Terminé", foreground=VERT)
        self._ecrire("✓ Aucune valeur d'origine retrouvée : squelette lisible "
                     "et diffusable.\n", "ok")

    def _ouvrir_dossier(self):
        if not self.dernier_dossier or not os.path.isdir(self.dernier_dossier):
            return
        try:
            os.startfile(self.dernier_dossier)  # noqa: S606 — Windows, dossier connu
        except (AttributeError, OSError):
            try:
                subprocess.Popen(["explorer", self.dernier_dossier])
            except OSError as exc:
                messagebox.showerror("Ouverture impossible", str(exc))

    def _vider(self):
        self.txt.configure(state="normal")
        self.txt.delete("1.0", "end")
        self.txt.configure(state="disabled")

    def _ecrire(self, texte, tag=None):
        self.txt.configure(state="normal")
        self.txt.insert("end", texte, tag or "")
        self.txt.see("end")
        self.txt.configure(state="disabled")


def main(argv=None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    cas = argv[0] if argv else ""
    sortie = argv[1] if len(argv) > 1 else ""
    root = tk.Tk()
    ui = SqueletteUI(root, cas, sortie)
    if cas:
        ui._decrire_cas()
    root.mainloop()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
