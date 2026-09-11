# IntellaFeeder — Wiki Presentation

*(English version — [version française plus bas](#intellafeeder-fr-1))*

## What is IntellaFeeder?

IntellaFeeder is a free, standalone Windows GUI tool that prepares and drives
bulk source imports into **Vound Intella Investigator 3.1**, using its
command-line companion `IntellaCmd.exe -addSourcesFromJson`. It is written in
Python (Tkinter, standard library only) and distributed as a single `.exe`
(PyInstaller), with no installation or external dependency.

It does not replace Intella — it only automates the repetitive, error-prone
part of adding many sources (forensic images, folders, files) to an existing
case: writing correct JSON descriptors, attaching per-source task files,
staying under a size limit, and producing a script that can be launched
unattended.

## Why it exists

Adding sources one by one through Intella's web wizard does not scale once a
case involves dozens or hundreds of paths (disk images, custodian folders,
loose files). Doing this reliably by hand is slow and error-prone: forgetting
a required field, mixing up a multi-segment image's first vs. non-first
segment, exceeding the case size limit mid-way, or losing track of which
sources were already indexed.

IntellaFeeder turns that into: paste paths → review a table → tick boxes →
click "Generate" → run the resulting `.bat`.

## Core workflow

Since v3 the window is organised as a **two-step trail** — the actual job —
with four **tools** kept to one side. Each step carries a state (to do / in
progress / done) computed from real progress, so the trail is a map of where
you are, not a row of tabs in disguise.

1. **① The case**: point the tool at an existing case folder. It reads
   `case.xml` for identity/size, then calls `IntellaCmd.exe -exportSourceList`
   to list sources already indexed — used both to display the case's current
   content and to avoid double-indexing. Reading a case also teaches the tool
   the MIME type names Intella writes in that case's filters.
2. **② Import sources**: paste one path per line (forensic images on one side,
   folders/files on the other). "Analyse paths" builds the list of sources to
   import and measures the ones with no size yet — already-indexed sources are
   struck through rather than removed. Tick which annex tasks to run per source
   (dynamic T1/T2… columns, one per task in the loaded task file; the real task
   name is in the column's tooltip), pick an analysis profile per source, then
   run the whole import with one button.

The tools, on the right of the trail:

- **Case detail**: a read-only, human-friendly view of `case.xml`,
  `case.prefs` and the case's task list (`tasks2.json`).
- **Profiles**: named sets of Intella indexing options, in two sub-tabs —
  *Settings* (the thematic form) and *File types to index* (the MIME filter,
  composed by picking entries from the reference list; see below).
- **Maintenance**: the activity log (searchable, filtered by All / Warnings /
  Errors), the preferences (language, density, text scale), the MIME type
  reference list, and a "Files" screen saying where everything lives.
- **Help**: end-user oriented, searchable, with drawn diagrams (the trail, the
  include/exclude filter, a multi-segment image).

## What gets generated

For each source, IntellaFeeder writes:

- one JSON descriptor (`name`, `evidencePath`, `sourceType`, `timezone`,
  merged profile options, optional `taskFile`);
- if any task combination is ticked for that source, a matching task file
  (a verbatim subset of the loaded task file, so task UUIDs — and therefore
  any pre-existing task results in the case — stay valid);
- one `IntellaCmd.exe -addSourcesFromJson` command inside a single `.bat`
  script for the whole batch, each command's output redirected to its own log
  file under a timestamped run folder.

The `.bat` is **resilient**: one command per source means a single source
failing does not abort the rest of the batch. A "Valider les opérations"
button re-reads the latest run's logs afterwards to confirm what actually got
imported.

## Size guard-rail (no automatic compound cases)

Intella case size is practically limited. IntellaFeeder computes the volume
already present in the case (the larger of `case.xml`'s reported size and the
inventory's measured total, to stay safe) plus the new sources selected for
import. If the total exceeds the configured limit (950 GB by default,
adjustable, fractional GB allowed):

- the tool **does not** create a compound sub-case automatically;
- it **warns**, automatically **unticks** the excess sources (sequential
  cut — the top of the list is what fits, the rest is left for later), and
  **suspends generation** — nothing is written to disk;
- the user adjusts the "Imp." checkboxes and clicks "Générer" again for what
  fits, then manually creates the sub-case in Intella, targets it as the
  active case, and re-ticks/re-imports the remainder.

A source larger than the limit on its own is flagged as "cannot be split."

## Known Intella limitation and built-in workaround

Vound Intella has a known issue where the built-in integrity check can fail
on forensic images split into multiple segments (`.E01/.E02…`, `.ad1/.ad2…`).
IntellaFeeder's Import tab exposes a "Do not verify source integrity"
checkbox; when ticked, it automatically appends `-validateDiskImage false` to
the IntellaCmd command line, and remembers the choice per case. This is a
workaround for the multi-segment case, not a general recommendation to skip
integrity checking.

## Bilingual by design

The UI, help text, and all validation/error messages are available in French
and English. Translations live in two places: `lang/FR.lang` and
`lang/US.lang` (plain JSON, editable without recompiling, take priority if
present) and `lang_data.py` (the same content embedded in the executable by
PyInstaller as an ordinary Python module, so the tool is fully bilingual even
without the `lang/` folder). Adding a new language only requires dropping a
new `lang/<CODE>.lang` file — it appears in the language selector without a
rebuild.

## MIME type reference

Intella identifies what it indexes by MIME type name, and a source's type
filter is a plain list of those names. Two things make that list hard to read,
and IntellaFeeder handles both:

- **A filter is read backwards if its mode is left unsaid.** In Intella's GUI
  you tick what you *want*; the export records the *complement*, so
  `Exclude selected entries` followed by six hundred types means those six
  hundred are the ones left out. IntellaFeeder always states, in colour, what
  the list actually does — red for "these types are excluded", green for "only
  these types are indexed".
- **Intella writes synonyms it never describes.** Measured on a near-exhaustive
  real filter: 18 % of the names have no label anywhere in Vound's description
  file (five different names for a Word document alone). Treating those as
  errors would paint a hundred lines red on a normal source, so the reference
  list has **four states** — described by Vound, described by you, known but
  unlabelled, and genuinely unknown.

679 descriptions and 800 observed names ship **inside the executable**; the
tool learns new names from every case it reads, and an Intella
`.properties` file can be imported to add its labels (imports accumulate,
they never replace what is already known).

## Analysis profiles in depth

A profile is a named, reusable subset of the options accepted by
`-addSourcesFromJson` (mail archive indexing, chat processing mode/split,
embedded-image indexing, paragraph analysis, email geolocation, binary size
cap, archive/database/registry/event-log/browser-history indexing, deleted
item recovery, MIME and file-name filters…). The catalog knows each option's
default so that only the values that differ from Intella's own defaults are
written into the generated JSON — a profile named "default" always means
"don't touch anything, use Intella's defaults."

Profiles are stored as individual JSON files in a `profils/` folder next to
the executable, so they can be backed up or shared between installations
independently of the `.ini` settings file.

**What a profile cannot do, and says so.** `-addSourcesFromJson` accepts a
white list of option names and silently drops everything else — a setting
Intella can store is not necessarily a setting its automatic import can
replay. Rather than pretend otherwise, the "Source settings" viewer shows every
setting of an exported source in three colours: replayed by the profile,
known but to be redone by hand in Intella, and unknown (which almost always
means your Intella is newer than the tool's catalogue).

## Technical notes

- **Platform**: Windows only (Tkinter GUI), packaged as a single `.exe` via
  PyInstaller; also runnable directly from Python 3.10+ sources with zero
  third-party dependencies.
- **Persistence**: `intellafeeder.ini` for common/per-case settings, one
  `IF_<case>.info` JSON file per case (folder-size cache, integrity-check
  preference), one JSON file per analysis profile.
- **License**: MIT.
- **Repository**: public on GitHub, MIT-licensed — issues and contributions
  welcome.

---

<a id="intellafeeder-fr-1"></a>
# IntellaFeeder — Présentation pour le wiki (FR)

*(Version anglaise plus haut — [English version above](#intellafeeder--wiki-presentation))*

## Qu'est-ce qu'IntellaFeeder ?

IntellaFeeder est un outil Windows gratuit et autonome, avec interface
graphique, qui prépare et pilote l'import en masse de sources dans
**Vound Intella Investigator 3.1**, via son compagnon en ligne de commande
`IntellaCmd.exe -addSourcesFromJson`. Écrit en Python (Tkinter, bibliothèque
standard uniquement) et distribué sous forme d'un exécutable unique
(PyInstaller), sans installation ni dépendance externe.

Il ne remplace pas Intella : il automatise seulement la partie répétitive et
propice aux erreurs de l'ajout de nombreuses sources (images forensiques,
dossiers, fichiers) à un cas existant — écrire des descripteurs JSON corrects,
attacher des fichiers de tâches par source, rester sous une limite de volume,
et produire un script exécutable sans surveillance.

## Pourquoi cet outil

Ajouter des sources une par une via l'assistant web d'Intella ne passe pas à
l'échelle dès qu'un cas comporte des dizaines ou des centaines de chemins
(images disque, dossiers de personnes concernées, fichiers isolés). Le faire
fiablement à la main est lent et propice aux erreurs : champ obligatoire
oublié, confusion entre le premier et un autre tronçon d'une image
multi-segments, dépassement de la limite de volume du cas en cours de route,
ou perte de vue des sources déjà indexées.

IntellaFeeder ramène tout cela à : coller des chemins → relire un tableau →
cocher des cases → cliquer « Générer » → lancer le `.bat` produit.

## Déroulé général

Depuis la v3, la fenêtre s'organise en un **fil de deux étapes** — le travail
lui-même — et quatre **outils** rangés à côté. Chaque étape porte un état
(à faire / en cours / fait) calculé sur l'avancement réel : le fil dit où l'on
en est, il n'est pas une barre d'onglets déguisée.

1. **① Le cas** : on pointe l'outil vers un dossier de cas existant. Il lit
   `case.xml` (identité/taille) puis appelle `IntellaCmd.exe
   -exportSourceList` pour lister les sources déjà indexées — utilisé à la fois
   pour afficher le contenu actuel du cas et pour éviter la double indexation.
   Lire un cas apprend aussi à l'outil les noms de types MIME qu'Intella écrit
   dans les filtres de ce cas.
2. **② Import des sources** : on colle un chemin par ligne (images forensiques
   d'un côté, dossiers/fichiers de l'autre). « Analyser les chemins » construit
   la liste des sources à importer et mesure celles qui n'ont pas encore de
   taille — les sources déjà indexées sont **barrées** plutôt que retirées. On
   coche, pour chaque source, les tâches annexes à exécuter (colonnes
   dynamiques T1, T2…, une par tâche du fichier chargé ; le nom réel de la
   tâche est dans l'infobulle de la colonne), on choisit un profil d'analyse
   par source, puis un seul bouton enchaîne tout l'import.

Les outils, à droite du fil :

- **Détail du cas** : vue lecture seule et humanisée de `case.xml`,
  `case.prefs` et de la liste des tâches du cas (`tasks2.json`).
- **Profils** : jeux nommés d'options d'indexation Intella, en deux
  sous-onglets — *Réglages* (le formulaire thématique) et *Types de fichiers à
  indexer* (le filtre MIME, composé en prenant des entrées dans le
  référentiel ; voir plus bas).
- **Maintenance** : le journal d'activité (cherchable, filtré Tout / Alertes /
  Erreurs), les préférences (langue, densité, taille du texte), le référentiel
  de types MIME, et un écran « Fichiers » qui dit où tout se range.
- **Aide** : destinée à l'utilisateur final, cherchable, avec des schémas
  dessinés (le parcours, le filtre include/exclude, une image multi-tronçons).

## Ce qui est généré

Pour chaque source, IntellaFeeder écrit :

- un descripteur JSON (`name`, `evidencePath`, `sourceType`, `timezone`,
  options du profil fusionnées, `taskFile` optionnel) ;
- si une combinaison de tâches est cochée pour cette source, un fichier de
  tâches correspondant (sous-ensemble verbatim du fichier de tâches chargé,
  afin que les UUID de tâches — et donc les résultats de tâches déjà
  existants dans le cas — restent valides) ;
- une commande `IntellaCmd.exe -addSourcesFromJson` par source, regroupées
  dans un seul script `.bat` pour tout le lot, chaque sortie redirigée vers
  son propre fichier de log sous un dossier de run horodaté.

Le `.bat` est **résilient** : une commande par source signifie qu'une seule
source en échec n'interrompt pas les autres. Un bouton « Valider les
opérations » relit ensuite les logs du run le plus récent pour confirmer ce
qui a réellement été importé.

## Garde-fou de volume (pas de cas composé automatique)

Le volume d'un cas Intella est limité en pratique. IntellaFeeder calcule le
volume déjà présent dans le cas (le plus grand entre la taille annoncée par
`case.xml` et le total mesuré de l'inventaire, par prudence) plus les
nouvelles sources sélectionnées pour l'import. Si le total dépasse la limite
configurée (950 Go par défaut, ajustable, en Go fractionnaires) :

- l'outil **ne crée pas** de sous-cas composé automatiquement ;
- il **avertit**, **décoche** automatiquement les sources en surplus (coupe
  séquentielle — le haut de la liste est ce qui tient, le reste est laissé
  pour plus tard), et **suspend la génération** — rien n'est écrit sur le
  disque ;
- l'utilisateur ajuste les cases « Imp. » puis relance « Générer » pour ce
  qui tient, puis crée manuellement le sous-cas dans Intella, le cible comme
  cas actif, et recoche/réimporte le reste.

Une source à elle seule plus grande que la limite est signalée comme « non
fractionnable ».

## Limitation connue d'Intella et contournement intégré

Vound Intella présente un problème connu : la vérification d'intégrité
intégrée peut échouer sur des images forensiques découpées en plusieurs
tronçons (`.E01/.E02…`, `.ad1/.ad2…`). L'onglet Import d'IntellaFeeder propose
une case « Ne pas vérifier l'intégrité des sources » ; une fois cochée, elle
ajoute automatiquement `-validateDiskImage false` à la ligne de commande
IntellaCmd, et mémorise ce choix par cas. C'est un contournement pour le cas
multi-tronçons, pas une recommandation générale de désactiver la vérification
d'intégrité.

## Multi-langue par conception

L'interface, l'aide et tous les messages de validation/erreur sont disponibles
en français et en anglais. Les traductions vivent à deux endroits :
`lang/FR.lang` et `lang/US.lang` (JSON simple, éditable sans recompiler,
prioritaire s'il est présent) et `lang_data.py` (le même contenu embarqué dans
l'exécutable par PyInstaller comme un module Python normal, pour que l'outil
reste bilingue même sans le dossier `lang/`). Ajouter une langue ne demande que
de déposer un fichier `lang/<CODE>.lang` — il apparaît dans le sélecteur de
langue sans recompiler.

## Le référentiel de types MIME

Intella désigne ce qu'il indexe par des noms de types MIME, et le filtre de
types d'une source n'est qu'une liste de ces noms. Deux choses rendent cette
liste difficile à lire, et l'outil traite les deux :

- **Un filtre se lit à l'envers si l'on tait son mode.** Dans l'interface
  d'Intella on coche ce qu'on **veut**, et l'export enregistre le
  **complément** : `Exclude selected entries` suivi de six cents types signifie
  que ces six cents-là sont écartés. IntellaFeeder dit toujours, en couleur, ce
  que la liste fait réellement — rouge pour « ces types sont exclus », vert
  pour « seuls ces types sont indexés ».
- **Intella écrit des synonymes qu'il ne décrit nulle part.** Mesuré sur un
  filtre réel quasi exhaustif : 18 % des noms n'ont de libellé nulle part dans
  le fichier de descriptions de Vound (cinq noms différents pour le seul
  document Word). Les traiter comme des erreurs peindrait cent lignes en rouge
  sur une source normale — d'où **quatre états** au référentiel : décrit par
  Vound, décrit par vous, connu sans libellé, et réellement inconnu.

679 descriptions et 800 noms observés sont **embarqués dans l'exécutable** ;
l'outil apprend de nouveaux noms à chaque cas lu, et un fichier `.properties`
d'Intella peut être importé pour ajouter ses libellés (les imports
s'accumulent, ils ne remplacent jamais ce qui est déjà connu).

## Les profils d'analyse en détail

Un profil est un sous-ensemble nommé et réutilisable des options acceptées par
`-addSourcesFromJson` (indexation des archives de messagerie, mode/découpage
de traitement des conversations, indexation des images intégrées, analyse des
paragraphes, géolocalisation des e-mails, taille maximale des binaires stockés,
indexation des archives/bases de données/registre/journaux d'événements/
historique navigateur, récupération d'éléments supprimés, filtres MIME et de
nom de fichier…). Le catalogue connaît la valeur par défaut de chaque option,
si bien que seules les valeurs qui diffèrent des défauts Intella sont écrites
dans le JSON généré — un profil nommé « défaut » signifie toujours « ne rien
changer, utiliser les défauts d'Intella ».

Les profils sont stockés en fichiers JSON individuels dans un dossier
`profils/` à côté de l'exécutable, ce qui permet de les sauvegarder ou de les
partager entre installations indépendamment du fichier de réglages `.ini`.

**Ce qu'un profil ne peut pas faire, et le dit.** `-addSourcesFromJson` ne
connaît qu'une liste blanche de noms d'options et jette le reste **en
silence** : un réglage qu'Intella sait enregistrer n'est pas forcément un
réglage que son import automatique sait rejouer. Plutôt que de laisser croire
le contraire, le visualiseur « Réglages de la source » montre tous les réglages
d'une source exportée en trois couleurs : rejoué par le profil, connu mais à
refaire à la main dans Intella, et inconnu (ce qui signale presque toujours un
Intella plus récent que le catalogue de l'outil).

## Notes techniques

- **Plateforme** : Windows uniquement (interface Tkinter), packagé en un seul
  exécutable via PyInstaller ; exécutable aussi directement depuis les sources
  Python 3.10+ sans aucune dépendance tierce.
- **Persistance** : `intellafeeder.ini` pour les réglages communs/par cas, un
  fichier JSON `IF_<cas>.info` par cas (cache des tailles de dossiers,
  préférence de vérification d'intégrité), un fichier JSON par profil
  d'analyse.
- **Licence** : MIT.
- **Dépôt** : public sur GitHub, sous licence MIT — issues et contributions
  bienvenues.
