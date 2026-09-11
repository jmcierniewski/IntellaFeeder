# IntellaFeeder

*(English version below — [version française plus bas](#intellafeeder-fr))*

Automatic source-import generator for **Vound Intella Investigator 3.1**, driving
`IntellaCmd.exe -addSourcesFromJson`. Tkinter GUI, bilingual (EN/FR), no external
dependency (Python standard library only).

Avoids the repetitive clicks of the Intella web wizard: paste lists of paths
(forensic images / folders), pick per-source tasks and analysis profile, and the
tool generates the JSON files plus a resilient `.bat` script (one IntellaCmd
command per source, continues after a failure) ready to run.

## Interface (v3)

> What changed since v2.5, and why: **[V3.md](V3.md)**.

The window is a **two-step trail** — ① the case, ② import sources — with four
tools alongside it (case detail, profiles, maintenance, help). Each step
carries a state computed from real progress. Density and text scale are
adjustable from Maintenance → Options, so the same window works on a 13″
laptop and on a 27″ desk screen.

## Features

- **Case inventory**: reads sources already indexed in a case (`-exportSourceList`),
  automatic de-duplication, size guard-rail (`case.xml` vs. measured total).
- **Import**: paste paths, per-source tasks (reuses an existing Intella task file
  as-is), configurable per-case size guard-rail, post-import validation (log
  re-scan).
- **Analysis profiles**: named sets of indexing options (MIME filters, archives,
  deleted-file recovery, VSS…), reusable across cases, importable from a source
  already configured in Intella ("Info Profil").
- **MIME type reference**: 679 descriptions and 800 type names built into the
  executable, enriched automatically from every case you read. A source's type
  filter is shown with what it actually *does* (exclude vs. include, in
  colour), and four states tell a valid-but-unlabelled synonym apart from a
  genuinely unknown name — 18 % of a real filter is the former.
- **Maintenance**: activity log (searchable, All / Warnings / Errors),
  preferences, MIME reference, and a "Files" screen telling you where
  everything lives.
- **Bilingual**: French and English built into the executable; adding a language
  requires no rebuild (see `lang/`, which is optional — Maintenance → Files →
  "Write the languages here…" seeds it).
- **Known Vound multi-segment image bug — built-in workaround**: Intella's own
  integrity check can fail on forensic images split into multiple segments
  (`.E01/.E02…`, `.ad1/.ad2…`). The Import tab exposes a "Do not verify source
  integrity" checkbox that automatically adds `-validateDiskImage false` to the
  IntellaCmd arguments, remembered per case. See the in-app Help tab for details.

## Requirements

- Windows, with **Vound Intella Investigator 3.1** installed (`IntellaCmd.exe`).
- Python 3.10+ if run from source (no package to install, standard library only —
  `tkinter` ships with the official Python installer).

## Usage

From source:

```powershell
python intellaFeeder.py
```

An `intellafeeder.ini` file is created on first launch (common and per-case
settings). `tasks.json` (next to the script) is the default task file.

## Building the executable

```powershell
pyinstaller --onefile --noconsole --name IntellaFeeder intellaFeeder.py
```

`tasks.json` stays external (next to the exe, editable); FR/EN languages are
embedded in the exe (`lang_data.py`) — the `lang/` folder is optional, but can be
shipped alongside the exe to add or fix a translation without rebuilding (see
`i18n.py`).

## Tests

```powershell
python -m pip install -r requirements-dev.txt
python -m pytest
```

432 tests, about 3 seconds. The suite covers the non-GUI modules only (path
parsing, sizing, task files, import JSON, profile catalog and XML translation,
log analysis, case info file, upfront validation, MIME reference): no
IntellaCmd, no network. pytest is a **development** dependency — the
application itself needs the standard library only.

The GUI is checked by two scripts instead, since pytest covers no widget:

```powershell
python tests\manuel_construction.py        # builds the window WITHOUT showing it
python tests\manuel_fumee_v3.py <screen>   # opens it on one screen, to look at
```

`manuel_construction.py` never steals focus, so it is usable while someone is
working on the machine — it is what caught a profile filter silently losing its
value.

## Architecture

Modular layout (one module = one responsibility): see the docstring at the top
of each file. Entry points: `intellaFeeder.py` (launch), `ui.py` (main window),
`generator.py` (output generation).

## License

MIT — see [LICENSE](LICENSE).

---

<a id="intellafeeder-fr"></a>
# IntellaFeeder (FR)

*(Version anglaise plus haut — [English version above](#intellafeeder))*

Générateur d'import automatique de sources pour **Vound Intella Investigator 3.1**,
via `IntellaCmd.exe -addSourcesFromJson`. Interface graphique (Tkinter), multi-langue
(FR/EN), sans dépendance externe (bibliothèque standard Python uniquement).

Évite les clics répétitifs de l'assistant web Intella : on colle des listes de
chemins (images forensiques / dossiers), on choisit les tâches et le profil
d'analyse à appliquer par source, et l'outil génère les fichiers JSON et un
script `.bat` résilient (1 commande IntellaCmd par source, poursuit après un
échec) prêt à lancer.

## Interface (v3)

> Ce qui a changé depuis la v2.5, et pourquoi : **[V3.md](V3.md)**.

La fenêtre est un **fil de deux étapes** — ① le cas, ② l'import des sources —
avec quatre outils à côté (détail du cas, profils, maintenance, aide). Chaque
étape porte un état calculé sur l'avancement réel. La densité et la taille du
texte se règlent dans Maintenance → Options : la même fenêtre sert sur un
portable 13″ comme sur un écran de bureau de 27″.

## Fonctionnalités

- **Inventaire du cas** : lit les sources déjà indexées (`-exportSourceList`),
  dédoublonnage automatique, garde-fou de volume (`case.xml` vs somme mesurée).
- **Import** : collage de chemins, tâches par source (fichier de tâches
  Intella réutilisé tel quel), garde-fou de taille par cas configurable,
  validation post-import (relecture des logs).
- **Profils d'analyse** : jeux de paramètres d'indexation nommés (filtres MIME,
  archives, VSS…), réutilisables entre cas, importables depuis une source déjà
  réglée dans Intella (« Info Profil »).
- **Référentiel de types MIME** : 679 descriptions et 800 noms de types
  embarqués dans l'exécutable, enrichis automatiquement à chaque cas lu. Le
  filtre de types d'une source est affiché avec ce qu'il **fait** réellement
  (exclure ou inclure, en couleur), et quatre états distinguent un synonyme
  valide mais sans libellé d'un nom réellement inconnu — 18 % d'un filtre réel
  relèvent du premier cas.
- **Maintenance** : journal d'activité (cherchable, Tout / Alertes / Erreurs),
  préférences, référentiel MIME, et un écran « Fichiers » qui dit où tout se
  range.
- **Multi-langue** : français et anglais intégrés à l'exécutable ; ajout d'une
  langue possible sans recompiler (voir `lang/`, facultatif — Maintenance →
  Fichiers → « Écrire les langues ici… » le remplit).
- **Bug connu Vound sur les images multi-tronçons — contournement intégré** : la
  vérification d'intégrité d'Intella peut échouer sur des images forensiques
  découpées en plusieurs fichiers (`.E01/.E02…`, `.ad1/.ad2…`). L'onglet Import
  propose une case « Ne pas vérifier l'intégrité des sources » qui ajoute
  automatiquement `-validateDiskImage false` aux arguments IntellaCmd, mémorisée
  par cas. Voir l'onglet Aide de l'application pour le détail.

## Prérequis

- Windows, avec **Vound Intella Investigator 3.1** installé (`IntellaCmd.exe`).
- Python 3.10+ si lancé depuis les sources (aucun paquet à installer, seulement
  la bibliothèque standard — `tkinter` inclus avec l'installeur officiel Python).

## Utilisation

Depuis les sources :

```powershell
python intellaFeeder.py
```

Un fichier `intellafeeder.ini` est créé au premier lancement (paramètres
communs et par cas). `tasks.json` (à côté du script) sert de fichier de tâches
par défaut.

## Construire l'exécutable

```powershell
pyinstaller --onefile --noconsole --name IntellaFeeder intellaFeeder.py
```

`tasks.json` reste externe (à côté de l'exe, éditable) ; les langues FR/US sont
embarquées dans l'exe (`lang_data.py`) — le dossier `lang/` est facultatif,
mais peut être livré à côté pour permettre d'ajouter/corriger une traduction
sans recompiler (voir `i18n.py`).

## Tests

```powershell
python -m pip install -r requirements-dev.txt
python -m pytest
```

432 tests, environ 3 secondes. La suite couvre uniquement les modules **sans
interface** (analyse de chemins, calcul de tailles, fichiers de tâches, JSON
d'import, catalogue de profils et traduction XML, analyse des logs, fichier
d'info du cas, validation amont, référentiel MIME) : pas d'IntellaCmd, pas de
réseau. pytest est une dépendance de **développement** — l'application, elle,
n'utilise que la bibliothèque standard.

L'interface se vérifie par deux scripts, puisqu'aucun widget n'est couvert par
pytest :

```powershell
python tests\manuel_construction.py        # construit la fenêtre SANS l'afficher
python tests\manuel_fumee_v3.py <écran>    # l'ouvre sur un écran, pour regarder
```

`manuel_construction.py` ne vole jamais le focus : il reste utilisable pendant
que quelqu'un travaille sur le poste — c'est lui qui a attrapé un filtre de
profil qui perdait sa valeur en silence.

## Architecture

Découpage modulaire (1 module = 1 responsabilité) : voir les docstrings en
tête de chaque fichier. Points d'entrée : `intellaFeeder.py` (lancement),
`ui.py` (fenêtre principale), `generator.py` (génération des sorties).

## Licence

MIT — voir [LICENSE](LICENSE).
