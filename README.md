# IntellaFeeder

*(English version below — [version française plus bas](#intellafeeder-fr))*

Automatic source-import generator for **Vound Intella Investigator 3.1**, driving
`IntellaCmd.exe -addSourcesFromJson`. Tkinter GUI, bilingual (EN/FR), no external
dependency (Python standard library only).

Avoids the repetitive clicks of the Intella web wizard: paste lists of paths
(forensic images / folders), pick per-source tasks and analysis profile, and the
tool generates the JSON files plus a resilient `.bat` script (one IntellaCmd
command per source, continues after a failure) ready to run.

## Features

- **Case inventory**: reads sources already indexed in a case (`-exportSourceList`),
  automatic de-duplication, size guard-rail (`case.xml` vs. measured total).
- **Import**: paste paths, per-source tasks (reuses an existing Intella task file
  as-is), configurable per-case size guard-rail, post-import validation (log
  re-scan).
- **Analysis profiles**: named sets of indexing options (MIME filters, archives,
  deleted-file recovery, VSS…), reusable across cases, importable from a source
  already configured in Intella ("Info Profil").
- **Bilingual**: French and English built into the executable; adding a language
  requires no rebuild (see `lang/`).
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

## Fonctionnalités

- **Inventaire du cas** : lit les sources déjà indexées (`-exportSourceList`),
  dédoublonnage automatique, garde-fou de volume (`case.xml` vs somme mesurée).
- **Import** : collage de chemins, tâches par source (fichier de tâches
  Intella réutilisé tel quel), garde-fou de taille par cas configurable,
  validation post-import (relecture des logs).
- **Profils d'analyse** : jeux de paramètres d'indexation nommés (filtres MIME,
  archives, VSS…), réutilisables entre cas, importables depuis une source déjà
  réglée dans Intella (« Info Profil »).
- **Multi-langue** : français et anglais intégrés à l'exécutable ; ajout d'une
  langue possible sans recompiler (voir `lang/`).
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

## Architecture

Découpage modulaire (1 module = 1 responsabilité) : voir les docstrings en
tête de chaque fichier. Points d'entrée : `intellaFeeder.py` (lancement),
`ui.py` (fenêtre principale), `generator.py` (génération des sorties).

## Licence

MIT — voir [LICENSE](LICENSE).
