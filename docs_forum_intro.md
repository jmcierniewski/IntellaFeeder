# Forum introduction — IntellaFeeder

## English

Hi all,

I'd like to share **IntellaFeeder**, a small free tool I built to automate
bulk source imports into Intella Investigator via `IntellaCmd.exe
-addSourcesFromJson`. Instead of clicking through the web wizard for every
image/folder, you paste a list of paths, tick a few boxes (tasks, analysis
profile per source), and it generates the JSON descriptors plus a resilient
`.bat` script (one IntellaCmd command per source, so one failure doesn't stop
the rest) ready to run.

A few things it handles along the way: reading a case's existing sources to
avoid double-indexing, a size guard-rail that warns and lets you hold back the
overflow instead of silently failing, reusable named "analysis profiles" for
indexing options (that you can even reverse-engineer from a source already
configured in Intella's own GUI), and a workaround for the known integrity-check
issue on multi-segment images (`.E01/.E02…`). Windows only, packaged as a
single portable `.exe`, no install needed, bilingual FR/EN.

It's open source (MIT): https://github.com/jmcierniewski/IntellaFeeder

Happy to hear feedback, bug reports, or feature ideas.

---

## Français

Bonjour à tous,

Je partage **IntellaFeeder**, un petit outil gratuit que j'ai développé pour
automatiser l'import en masse de sources dans Intella Investigator via
`IntellaCmd.exe -addSourcesFromJson`. Plutôt que de cliquer dans l'assistant
web pour chaque image/dossier, on colle une liste de chemins, on coche
quelques cases (tâches, profil d'analyse par source), et l'outil génère les
descripteurs JSON ainsi qu'un script `.bat` résilient (une commande IntellaCmd
par source, donc un échec n'arrête pas les autres) prêt à lancer.

Quelques points gérés au passage : lecture des sources déjà présentes dans un
cas pour éviter la double indexation, un garde-fou de volume qui avertit et
permet de laisser de côté le surplus plutôt que d'échouer silencieusement,
des « profils d'analyse » nommés et réutilisables pour les options
d'indexation (qu'on peut même déduire d'une source déjà réglée dans la GUI
Intella elle-même), et un contournement du problème connu de vérification
d'intégrité sur les images multi-tronçons (`.E01/.E02…`). Windows uniquement,
packagé en un seul exécutable portable, aucune installation nécessaire,
bilingue FR/EN.

C'est open source (MIT) : https://github.com/jmcierniewski/IntellaFeeder

Vos retours, remontées de bugs ou idées de fonctionnalités sont les bienvenus.
