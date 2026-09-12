# Forum introduction — IntellaFeeder

## English

Hi all,

I'd like to share **IntellaFeeder**, a small free tool I built to automate
bulk source imports into Intella Investigator via `IntellaCmd.exe
-addSourcesFromJson`. Instead of clicking through the web wizard for every
image/folder, you build the list your way: paste paths from any tool
(Everything, PowerGrep, a home-made script), or drag-and-drop straight from
Explorer — whole folders onto the forensic-image side (it recursively picks
out every image's first segment only, never a mid-image `.E02`), or a
multi-selection of folders/files onto the other side (each drop becomes one
source, root folder only — Intella indexes everything under it). Sources
already in the case are de-duplicated automatically. Tick a few boxes (tasks,
analysis profile per source), and it generates the JSON descriptors plus a
resilient `.bat` script (one IntellaCmd command per source, so one failure
doesn't stop the rest) ready to run.

*Pasted paths turned into a list of sources, with per-source tasks and profile.*

![Import sources](https://github.com/jmcierniewski/IntellaFeeder/blob/main/Pictures/V3/04_Import%20sources.jpg)

A few things it handles along the way: reading a case's existing sources to
avoid double-indexing, a size guard-rail that warns and lets you hold back the
overflow instead of silently failing, reusable named "analysis profiles" for
indexing options (that you can even reverse-engineer from a source already
configured in Intella's own GUI), and a workaround for the known integrity-check
issue on multi-segment images (`.E01/.E02…`). Windows only, packaged as a
single portable `.exe`, no install needed, bilingual FR/EN.

Version 3 reworked the interface around the actual job: a two-step trail
(read the case → import the sources) instead of a row of tabs, a searchable
log, an illustrated in-app help, and adjustable density and text size so the
same window is usable on a laptop and on a large desk screen.

It's open source (MIT): https://github.com/jmcierniewski/IntellaFeeder

Happy to hear feedback, bug reports, or feature ideas.

---

## Français

Bonjour à tous,

Je partage **IntellaFeeder**, un petit outil gratuit que j'ai développé pour
automatiser l'import en masse de sources dans Intella Investigator via
`IntellaCmd.exe -addSourcesFromJson`. Plutôt que de cliquer dans l'assistant
web pour chaque image/dossier, on construit la liste à sa façon : collage de
chemins issus de n'importe quel outil (Everything, PowerGrep, un script
maison), ou glisser-déposer direct depuis l'Explorateur — des dossiers entiers
du côté images forensiques (seul le premier tronçon de chaque image est
récupéré, y compris en récursif, jamais un `.E02` isolé), ou une
multi-sélection de dossiers/fichiers de l'autre côté (chaque dépôt devient une
source, dossier racine uniquement — Intella indexe tout ce qu'il y a dessous).
Les sources déjà présentes dans le cas sont dédoublonnées automatiquement. On
coche quelques cases (tâches, profil d'analyse par source), et l'outil génère
les descripteurs JSON ainsi qu'un script `.bat` résilient (une commande
IntellaCmd par source, donc un échec n'arrête pas les autres) prêt à lancer.

*Les chemins collés, transformés en liste de sources avec tâches et profil par source.*

![Import des sources](https://github.com/jmcierniewski/IntellaFeeder/blob/main/Pictures/V3/04_Import%20sources.jpg)

Quelques points gérés au passage : lecture des sources déjà présentes dans un
cas pour éviter la double indexation, un garde-fou de volume qui avertit et
permet de laisser de côté le surplus plutôt que d'échouer silencieusement,
des « profils d'analyse » nommés et réutilisables pour les options
d'indexation (qu'on peut même déduire d'une source déjà réglée dans la GUI
Intella elle-même), et un contournement du problème connu de vérification
d'intégrité sur les images multi-tronçons (`.E01/.E02…`). Windows uniquement,
packagé en un seul exécutable portable, aucune installation nécessaire,
bilingue FR/EN.

La version 3 a refondu l'interface autour du travail réel : un fil de deux
étapes (lire le cas → importer les sources) plutôt qu'une rangée d'onglets, un
journal cherchable, une aide intégrée illustrée, et une densité et une taille
de texte réglables — la même fenêtre sert sur un portable comme sur un grand
écran de bureau.

C'est open source (MIT) : https://github.com/jmcierniewski/IntellaFeeder

Vos retours, remontées de bugs ou idées de fonctionnalités sont les bienvenus.
