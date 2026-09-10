"""Onglet Aide : mode d'emploi destiné à l'utilisateur final.

Texte volontairement accessible (pas de détails techniques internes, pas de
changelog). Le contenu vient de ``i18n.help_content()`` — ``lang\\<CODE>.lang``,
ou les langues embarquées dans l'exe (``lang_data``).

**Trois choix de mise en page**, issus du chantier de lisibilité (07/09/2026) :

1. **Largeur de lecture plafonnée.** C'était le premier grief, avant même la
   typographie : sur un écran large, les lignes atteignaient 200 caractères et
   l'œil perdait le début de la ligne suivante. Le texte est maintenant tenu
   dans une colonne d'environ 90 caractères, centrée — les marges absorbent le
   reste (`_ajuster_marges`).
2. **Un sommaire cliquable.** Onze sections d'affilée sans moyen d'atteindre
   celle qu'on cherche : on lisait tout ou rien.
3. **Les avertissements se voient.** Style ``warn`` : ce qui peut coûter un
   import raté ne doit pas avoir la même graisse que le reste.
"""

import re
import tkinter as tk
from tkinter import ttk

import config
import i18n

# Largeur de la colonne de texte, en pixels. ~90 caractères en Segoe UI 10 :
# au-delà, l'œil rate le retour à la ligne ; en deçà, on hache les phrases.
LARGEUR_LECTURE = 760

# Repli minimal si AUCUNE langue n'est disponible (ni ``lang\``, ni les langues
# embarquées) — situation qui ne se produit pas sur un exe normalement
# construit. Il ne duplique volontairement PAS l'aide : une deuxième copie du
# texte dans le code vieillit sans qu'on s'en aperçoive (l'ancienne version
# énumérait encore des centaines de types MIME retirés de l'aide depuis).
_DEFAULT_CONTENT = [
    ("h1", f"{config.APP_NAME} — Aide"),
    ("p", "Le texte de l'aide n'a pas pu être chargé : ni le dossier « lang », "
          "ni les traductions intégrées ne sont disponibles."),
    ("warn", "Vérifiez que l'application n'a pas été déplacée sans ses fichiers, "
             "ou reconstruisez l'exécutable."),
]


class HelpTab(ttk.Frame):
    def __init__(self, parent, app):
        super().__init__(parent)
        self.app = app
        self._marques = []      # (titre, nom de marque) des sections de 1er niveau

        # --- Sommaire : une rangée de libellés cliquables ------------------ #
        self.sommaire = ttk.Frame(self)
        self.sommaire.pack(fill="x", padx=12, pady=(8, 4))

        holder = ttk.Frame(self)
        holder.pack(fill="both", expand=True, padx=8, pady=(0, 8))
        text = tk.Text(holder, wrap="word", state="disabled", padx=10, pady=10,
                       relief="flat", cursor="arrow")
        vsb = ttk.Scrollbar(holder, orient="vertical", command=text.yview)
        text.configure(yscrollcommand=vsb.set)
        text.pack(side="left", fill="both", expand=True)
        vsb.pack(side="right", fill="y")
        self.text = text
        holder.bind("<Configure>", self._ajuster_marges)

        text.tag_configure("h1", font=("Segoe UI", 13, "bold"),
                           foreground="#1e40af", spacing1=14, spacing3=6)
        text.tag_configure("h2", font=("Segoe UI", 11, "bold"), spacing1=8, spacing3=4)
        text.tag_configure("p", font=("Segoe UI", 10), spacing3=6, lmargin1=4, lmargin2=4)
        text.tag_configure("b", font=("Segoe UI", 10), spacing3=4,
                           lmargin1=16, lmargin2=28)
        # Avertissement : ce qui peut coûter un import raté. Fond ambré plutôt
        # que rouge — c'est une mise en garde, pas une erreur en cours.
        text.tag_configure("warn", font=("Segoe UI", 10, "bold"),
                           foreground="#7c2d12", background="#fef3c7",
                           spacing1=4, spacing3=6, lmargin1=16, lmargin2=16,
                           rmargin=8, borderwidth=0)
        # Séparateur bien visible entre types MIME (styles « pcsv »/« bcsv ») :
        # une puce « • » bleue en gras remplace la virgule (peu lisible).
        text.tag_configure("csvcomma", font=("Segoe UI", 11, "bold"), foreground="#2563eb")
        text.tag_raise("csvcomma")

        self._render()

    # ------------------------------------------------------------------ #
    def _ajuster_marges(self, event):
        """Centre la colonne de lecture : les marges absorbent la largeur en trop.

        Sans cela, l'aide s'étale sur toute la fenêtre — c'est ce qui la rendait
        pénible à lire sur un écran large.
        """
        marge = max(10, (event.width - LARGEUR_LECTURE) // 2)
        try:
            self.text.configure(padx=marge)
        except tk.TclError:
            pass

    def _insert_csv(self, body, base):
        """Insère ``body`` (tag ``base``) en remplaçant chaque virgule séparatrice
        par une puce « • » bleue en gras, bien plus lisible qu'une virgule."""
        parts = [p for p in re.split(r",\s*", body) if p]
        for i, part in enumerate(parts):
            if i:
                self.text.insert("end", "  •  ", (base, "csvcomma"))
            self.text.insert("end", part, base)

    def _aller_a(self, marque):
        self.text.see(marque)
        # `see` place la ligne n'importe où dans la vue ; `yview` la met en tête,
        # ce qui est le comportement attendu d'un sommaire.
        self.text.yview(f"{marque} linestart")

    def _build_sommaire(self):
        for w in self.sommaire.winfo_children():
            w.destroy()
        if len(self._marques) < 3:
            return          # deux sections : un sommaire n'apporte rien
        ttk.Label(self.sommaire, text=i18n.t("help.toc", "Aller à :"),
                  foreground="#475569").pack(side="left", padx=(0, 6))
        # Enveloppe qui passe à la ligne toute seule quand la fenêtre rétrécit.
        rangee = ttk.Frame(self.sommaire)
        rangee.pack(side="left", fill="x", expand=True)
        for titre, marque in self._marques:
            lien = tk.Label(rangee, text=titre, fg="#1d4ed8", cursor="hand2",
                            font=("Segoe UI", 9, "underline"))
            lien.pack(side="left", padx=(0, 12))
            lien.bind("<Button-1>", lambda _e, m=marque: self._aller_a(m))

    def _render(self):
        content = i18n.help_content() or _DEFAULT_CONTENT
        self.text.configure(state="normal")
        self.text.delete("1.0", "end")
        self._marques = []
        for style, body in content:
            if style == "h1":
                # Une marque par section : c'est la cible du sommaire. La toute
                # première (« IntellaFeeder — Aide ») n'y figure pas, ce n'est
                # pas une section mais le titre de la page.
                marque = f"sec{len(self._marques)}"
                self.text.mark_set(marque, "end-1c")
                self.text.mark_gravity(marque, "left")
                if self._marques or "—" not in body:
                    self._marques.append((body, marque))
                self.text.insert("end", body + "\n", "h1")
            elif style == "b":
                self.text.insert("end", "•  " + body + "\n", "b")
            elif style == "warn":
                self.text.insert("end", "⚠  " + body + "\n", "warn")
            elif style == "bcsv":                 # puce + virgules en gras
                self.text.insert("end", "•  ", "b")
                self._insert_csv(body, "b")
                self.text.insert("end", "\n", "b")
            elif style == "pcsv":                 # paragraphe + virgules en gras
                self._insert_csv(body, "p")
                self.text.insert("end", "\n", "p")
            else:
                self.text.insert("end", body + "\n", style)
        self.text.configure(state="disabled")
        self._build_sommaire()
