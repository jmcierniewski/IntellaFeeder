# IntellaFeeder

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
