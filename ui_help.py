"""Onglet Aide : mode d'emploi destiné à l'utilisateur final.

Texte volontairement accessible (pas de détails techniques internes, pas de
changelog). Le contenu vient de ``i18n.help_content()`` — ``lang\\<CODE>.lang``,
ou les langues embarquées dans l'exe (``lang_data``).

**Mise en page** — chantier de lisibilité du 07/09/2026, repris le 11/09/2026
parce que l'aide restait « trop compacte » : le contenu était jugé complet, mais
il fallait le *lire* pour le trouver.

1. **Largeur de lecture plafonnée.** Sur un écran large, les lignes atteignaient
   200 caractères et l'œil perdait le début de la ligne suivante.
2. **De l'air.** Interligne, espace avant les titres, retrait des puces : c'est
   ce qui sépare un texte qu'on parcourt d'un bloc qu'on affronte.
3. **Un sommaire cliquable** — onze sections d'affilée, sinon on lit tout ou rien.
4. **Une recherche** (11/09/2026), avec compteur et navigation d'occurrence en
   occurrence : sur une page de cette longueur, « où est-ce que ça parle de
   compound ? » n'avait pas de réponse.
5. **Des schémas** (11/09/2026) : trois notions se dessinent mieux qu'elles ne
   s'écrivent — le parcours, le sens d'un filtre, une image en plusieurs
   morceaux. Ils sont **dessinés** (Canvas), pas photographiés : une capture
   d'écran devient fausse à la première retouche d'interface, un schéma non.
6. **Les avertissements se voient.** Ce qui peut coûter un import raté ne doit
   pas avoir la même graisse que le reste.
"""

import re
import tkinter as tk
from tkinter import ttk

import config
import i18n
import ui_theme
from ui_widgets import attach_tip, make_button

# Largeur MAXIMALE de la colonne de texte, en pixels. Le texte l'occupe
# entièrement tant que la fenêtre est plus étroite ; au-delà, les marges
# absorbent le surplus plutôt que d'étirer les lignes.
#
# ⚠ Le plafond se règle en CARACTÈRES par ligne, pas en pixels : 760 → 1100 le
# 10/09/2026 (« l'aide ne prend que le milieu de l'écran »), puis 1100 → 820 le
# 11/09 — à 980 px et à la taille du corps de texte, les lignes faisaient encore
# ~150 caractères, soit très exactement ce que le plafond doit éviter. Avec la
# police de lecture (un point de plus que le reste), 820 px donnent ~95
# caractères, la fourchette confortable.
LARGEUR_LECTURE = 820

# Police du CORPS de l'aide : un point de plus que l'interface. Une page qui se
# lit d'un bout à l'autre n'a pas les mêmes besoins qu'un tableau qu'on balaie.
F_LECTURE = "IFHelpBody"
LARGEUR_SOMMAIRE = 230

SURLIGNE = "#fde68a"          # toutes les occurrences trouvées
SURLIGNE_ACTIF = "#f59e0b"    # celle où l'on se trouve

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
        self._hits = []         # positions trouvées par la recherche
        self._hit = -1
        self._figures = []      # Canvas insérés : gardés en référence

        self._build_recherche()

        corps = ttk.Frame(self)
        corps.pack(fill="both", expand=True)

        colonne = ttk.LabelFrame(corps, text=i18n.t("help.toc", "Aller à :"))
        colonne.pack(side="left", fill="y", padx=(app.theme.pad, 4), pady=6)
        self.sommaire = ttk.Frame(colonne, width=LARGEUR_SOMMAIRE)
        self.sommaire.pack(fill="both", expand=True, padx=6, pady=6)
        self.sommaire.pack_propagate(False)

        holder = ttk.Frame(corps)
        holder.pack(side="left", fill="both", expand=True,
                    padx=(4, app.theme.pad), pady=6)
        text = tk.Text(holder, wrap="word", state="disabled", padx=10, pady=14,
                       relief="flat", cursor="arrow",
                       background=config.UI_SURFACE, foreground=config.UI_INK,
                       highlightthickness=1, highlightbackground=config.UI_LINE)
        vsb = ttk.Scrollbar(holder, orient="vertical", command=text.yview)
        text.configure(yscrollcommand=vsb.set)
        text.pack(side="left", fill="both", expand=True)
        vsb.pack(side="right", fill="y")
        self.text = text
        holder.bind("<Configure>", self._ajuster_marges)
        self._police_lecture()
        self._styles()
        self._render()

    def _police_lecture(self):
        """Crée la police du corps de l'aide : celle de l'interface, +1 point.

        Nommée, donc elle suit le réglage de taille de Maintenance → Options
        comme le reste — mais avec un point d'avance, conservé à toutes les
        tailles.
        """
        import tkinter.font as tkfont
        base = tkfont.nametofont(ui_theme.F_BODY)
        try:
            self._font = tkfont.Font(root=self, name=F_LECTURE, exists=True)
        except tk.TclError:
            self._font = tkfont.Font(root=self, name=F_LECTURE,
                                     family=base.cget("family"),
                                     size=base.cget("size") + 1)

    # ------------------------------------------------------------------ #
    # Recherche                                                          #
    # ------------------------------------------------------------------ #
    def _build_recherche(self):
        bar = ttk.Frame(self)
        bar.pack(fill="x", padx=self.app.theme.pad, pady=(self.app.theme.pad, 0))
        ttk.Label(bar, text=i18n.t("help.search", "Rechercher dans l'aide")
                  + " :").pack(side="left")
        self.var_q = tk.StringVar()
        e = ttk.Entry(bar, textvariable=self.var_q, width=36)
        e.pack(side="left", padx=6)
        e.bind("<KeyRelease>", lambda _ev: self._chercher())
        e.bind("<Return>", lambda _ev: self._suivant(1))
        make_button(bar, "‹", lambda: self._suivant(-1), width=2).pack(side="left")
        make_button(bar, "›", lambda: self._suivant(1), width=2).pack(side="left", padx=2)
        self.lbl_hits = ttk.Label(bar, style="Hint.TLabel")
        self.lbl_hits.pack(side="left", padx=8)
        b = make_button(bar, i18n.t("help.search_clear", "Effacer"), self._effacer)
        b.pack(side="left")
        attach_tip(e, i18n.t(
            "help.search_tip",
            "Tapez un mot : toutes ses occurrences sont surlignées. « › » et « ‹ » "
            "sautent de l'une à l'autre, Entrée fait la même chose que « › »."))

    def _chercher(self):
        motif = self.var_q.get().strip()
        self.text.tag_remove("hit", "1.0", "end")
        self.text.tag_remove("hit_actif", "1.0", "end")
        self._hits, self._hit = [], -1
        if len(motif) < 2:
            self.lbl_hits.configure(text="")
            return
        depart = "1.0"
        while True:
            pos = self.text.search(motif, depart, stopindex="end", nocase=True)
            if not pos:
                break
            fin = f"{pos}+{len(motif)}c"
            self.text.tag_add("hit", pos, fin)
            self._hits.append(pos)
            depart = fin
        self.lbl_hits.configure(text=i18n.t("help.search_hits", "{n} résultat(s)",
                                            n=len(self._hits)))
        if self._hits:
            self._suivant(1)

    def _suivant(self, sens):
        if not self._hits:
            return
        self._hit = (self._hit + sens) % len(self._hits)
        motif = self.var_q.get().strip()
        pos = self._hits[self._hit]
        self.text.tag_remove("hit_actif", "1.0", "end")
        self.text.tag_add("hit_actif", pos, f"{pos}+{len(motif)}c")
        self.text.see(pos)
        self.lbl_hits.configure(text=i18n.t(
            "help.search_pos", "{i} / {n}", i=self._hit + 1, n=len(self._hits)))

    def _effacer(self):
        self.var_q.set("")
        self._chercher()

    # ------------------------------------------------------------------ #
    # Styles                                                             #
    # ------------------------------------------------------------------ #
    def _styles(self):
        t = self.text
        # Polices NOMMÉES : l'aide suit le réglage de taille de Maintenance →
        # Options, comme le reste de l'application.
        t.tag_configure("h1", font=ui_theme.F_TITLE, foreground=config.ACCENT,
                        spacing1=24, spacing3=10, lmargin1=0, lmargin2=0)
        t.tag_configure("h2", font=ui_theme.F_BOLD, foreground=config.UI_INK,
                        spacing1=14, spacing3=6)
        # `spacing2` = interligne DANS un paragraphe : c'est lui qui manquait le
        # plus. Un texte juste s'en trouve deux fois plus facile à parcourir.
        t.tag_configure("p", font=F_LECTURE, spacing2=4, spacing3=10,
                        lmargin1=2, lmargin2=2)
        t.tag_configure("b", font=F_LECTURE, spacing2=3, spacing3=7,
                        lmargin1=18, lmargin2=34)
        t.tag_configure("warn", font=ui_theme.F_BOLD, foreground="#7c2d12",
                        background="#fef3c7", spacing1=8, spacing2=3, spacing3=10,
                        lmargin1=18, lmargin2=18, rmargin=10)
        t.tag_configure("csvcomma", font=ui_theme.F_BOLD, foreground=config.ACCENT)
        t.tag_raise("csvcomma")
        t.tag_configure("hit", background=SURLIGNE)
        t.tag_configure("hit_actif", background=SURLIGNE_ACTIF)
        t.tag_raise("hit")
        t.tag_raise("hit_actif")

    def _ajuster_marges(self, event):
        """Centre la colonne de lecture : les marges absorbent la largeur en trop."""
        marge = max(10, (event.width - LARGEUR_LECTURE) // 2)
        try:
            self.text.configure(padx=marge)
        except tk.TclError:
            pass

    # ------------------------------------------------------------------ #
    # Schémas                                                            #
    # ------------------------------------------------------------------ #
    def _figure(self, nom):
        """Insère un schéma dans le flux du texte. Inconnu → rien, sans bruit."""
        dessin = {"parcours": self._fig_parcours,
                  "filtre": self._fig_filtre,
                  "segments": self._fig_segments}.get(nom)
        if dessin is None:
            return
        c = tk.Canvas(self.text, background=config.UI_SURFACE, highlightthickness=0,
                      width=640, height=110)
        dessin(c)
        self._figures.append(c)          # sinon le GC l'emporte
        self.text.window_create("end", window=c, padx=20, pady=8)
        self.text.insert("end", "\n", "p")

    @staticmethod
    def _boite(c, x, y, w, h, titre, sous, fond, bord, ink):
        c.create_rectangle(x, y, x + w, y + h, fill=fond, outline=bord, width=1)
        c.create_text(x + 12, y + 16, text=titre, anchor="w", fill=ink,
                      font=(ui_theme.F_BOLD,))
        if sous:
            c.create_text(x + 12, y + 36, text=sous, anchor="w",
                          fill=config.UI_INK_2, font=(ui_theme.F_SMALL,))

    @staticmethod
    def _fleche(c, x1, y, x2):
        c.create_line(x1, y, x2, y, arrow="last", fill=config.UI_INK_3, width=2)

    def _fig_parcours(self, c):
        self._boite(c, 10, 20, 230, 62,
                    i18n.t("help.fig_step1", "① Le cas"),
                    i18n.t("help.fig_step1_sub", "lire ce qui est déjà là"),
                    config.ACCENT_SOFT, config.ACCENT, config.ACCENT)
        self._fleche(c, 248, 51, 296)
        self._boite(c, 304, 20, 300, 62,
                    i18n.t("help.fig_step2", "② Import des sources"),
                    i18n.t("help.fig_step2_sub",
                           "coller → analyser → lancer l'import"),
                    config.ACCENT_SOFT, config.ACCENT, config.ACCENT)

    def _fig_filtre(self, c):
        vert, rouge = "#e7f5ec", "#fdeceb"
        self._boite(c, 10, 12, 290, 40, "include",
                    i18n.t("help.fig_include", "SEULS ces types sont indexés"),
                    vert, config.ACTION_COLOR, config.ACTION_COLOR)
        self._boite(c, 10, 60, 290, 40, "exclude",
                    i18n.t("help.fig_exclude", "ces types sont ÉCARTÉS"),
                    rouge, config.DANGER_COLOR, config.DANGER_COLOR)
        c.create_text(320, 20, anchor="nw", fill=config.UI_INK_2,
                      font=(ui_theme.F_SMALL,),
                      text=i18n.t("help.fig_filter_note",
                                  "Le défaut est « exclude ».\n"
                                  "Une liste composée comme « ce que je veux »\n"
                                  "fait alors exactement l'inverse."))

    def _fig_segments(self, c):
        x = 10
        for i in range(1, 6):
            actif = (i == 1)
            self._boite(c, x, 30, 96, 44,
                        f".E0{i}" if i < 5 else "…",
                        i18n.t("help.fig_first", "à indiquer") if actif else "",
                        config.ACCENT_SOFT if actif else config.UI_SURFACE_2,
                        config.ACCENT if actif else config.UI_LINE,
                        config.ACCENT if actif else config.UI_INK_3)
            x += 104
        c.create_text(10, 90, anchor="nw", fill=config.UI_INK_2,
                      font=(ui_theme.F_SMALL,),
                      text=i18n.t("help.fig_segments_note",
                                  "Une seule ligne à coller : le premier segment. "
                                  "Intella retrouve les autres tout seul."))

    # ------------------------------------------------------------------ #
    # Rendu                                                              #
    # ------------------------------------------------------------------ #
    def _insert_csv(self, body, base):
        """Remplace chaque virgule séparatrice par une puce « • » bleue en gras."""
        parts = [p for p in re.split(r",\s*", body) if p]
        for i, part in enumerate(parts):
            if i:
                self.text.insert("end", "  •  ", (base, "csvcomma"))
            self.text.insert("end", part, base)

    def _aller_a(self, marque):
        self.text.see(marque)
        self.text.yview(f"{marque} linestart")

    def _build_sommaire(self):
        for w in self.sommaire.winfo_children():
            w.destroy()
        if len(self._marques) < 3:
            self.sommaire.master.pack_forget()
            return
        if not self.sommaire.master.winfo_ismapped():
            self.sommaire.master.pack(side="left", fill="y",
                                      padx=(self.app.theme.pad, 4), pady=6)
        for titre, marque in self._marques:
            lien = tk.Label(self.sommaire, text="› " + titre, fg=config.ACCENT,
                            cursor="hand2",
                            anchor="w", justify="left", background=config.UI_BG,
                            wraplength=LARGEUR_SOMMAIRE - 16, pady=2,
                            font=ui_theme.F_BODY)
            lien.pack(fill="x", pady=1)
            lien.bind("<Button-1>", lambda _e, m=marque: self._aller_a(m))
            lien.bind("<Enter>", lambda _e, w=lien: w.config(
                fg=config.UI_INK, background=config.ACCENT_SOFT))
            lien.bind("<Leave>", lambda _e, w=lien: w.config(
                fg=config.ACCENT, background=config.UI_BG))

    def _render(self):
        content = i18n.help_content() or _DEFAULT_CONTENT
        self.text.configure(state="normal")
        self.text.delete("1.0", "end")
        self._marques = []
        self._figures = []
        for style, body in content:
            if style == "h1":
                marque = f"sec{len(self._marques)}"
                self.text.mark_set(marque, "end-1c")
                self.text.mark_gravity(marque, "left")
                if self._marques or "—" not in body:
                    self._marques.append((body, marque))
                self.text.insert("end", body + "\n", "h1")
            elif style == "fig":
                self._figure(body)
            elif style == "b":
                self.text.insert("end", "•  " + body + "\n", "b")
            elif style == "warn":
                self.text.insert("end", "⚠  " + body + "\n", "warn")
            elif style == "bcsv":
                self.text.insert("end", "•  ", "b")
                self._insert_csv(body, "b")
                self.text.insert("end", "\n", "b")
            elif style == "pcsv":
                self._insert_csv(body, "p")
                self.text.insert("end", "\n", "p")
            else:
                self.text.insert("end", body + "\n", style)
        self.text.configure(state="disabled")
        self._build_sommaire()
