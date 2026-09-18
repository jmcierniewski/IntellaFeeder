"""Calcul de la taille des sources : mesure unitaire + moteur de mesure en lot.

Deux niveaux :

1. **Mesure unitaire** — ``folder_size`` / ``image_size`` / ``source_size``.
   Chacune accepte ``on_progress`` (retour au fil de l'eau), ``should_stop``
   (interruption) et ``on_error`` (échec de lecture). Sur un NAS, un dossier
   peut demander des dizaines de minutes : sans ces crochets, l'utilisateur n'a
   ni visibilité, ni sortie de secours, ni moyen de savoir que le total est faux.
2. **Moteur en lot** — ``measure_sources`` : parcourt une liste d'éléments, gère
   le cache, la progression et l'annulation, et poste tout dans une ``queue``.
   Partagé par l'onglet Import (nouvelles sources) et l'onglet Inventaire
   (dossiers à 0). Ce module ne touche à AUCUN widget : c'est l'appelant qui
   draine la file sur le thread UI (tkinter n'est pas thread-safe).

⚠ **Contrat : une mesure incomplète n'est JAMAIS enregistrée.** Une taille
partielle ferait passer une source volumineuse sous la limite du cas. Deux
façons d'être incomplète, et il a fallu deux corrections pour les couvrir
toutes les deux :

- **Interruption** (``should_stop``) — une source arrêtée en cours de mesure est
  jetée, pas rendue.
- **Échec de lecture** (``on_error``, 18/09/2026) — un partage SMB qui se
  déconnecte à mi-parcours, un dossier devenu illisible, un fichier verrouillé.
  ``os.walk`` **avale ces erreurs en silence** et poursuit : la mesure se
  terminait donc « normalement », avec un total tronqué tenu pour complet,
  posté, mis en cache et persisté. C'est le scénario même que le contrat
  d'annulation prétendait empêcher, par une autre porte.

Les sources concernées ressortent dans ``failed`` (message ``done``) et restent
« à mesurer » : mieux vaut une mesure manquante, visible, qu'une mesure fausse.
"""

import os
import time

import config
import image_families
import path_parser

# Cadence minimale entre deux notifications de progression (secondes) : un
# dossier de plusieurs millions de fichiers saturerait sinon la file.
PROGRESS_INTERVAL = 0.2


class _Reporter:
    """Compteur de progression cadencé (fichiers, octets, chemin en cours)."""

    def __init__(self, on_progress):
        self.on_progress = on_progress
        self.files = 0
        self.bytes = 0
        # Démarre la fenêtre de cadence maintenant : la 1ʳᵉ notification « source
        # en cours » est déjà postée par measure_sources, inutile d'en émettre une
        # de plus dès le premier fichier.
        self._last = time.monotonic()

    def add(self, size: int, current: str, force: bool = False):
        self.files += 1
        self.bytes += size
        if not self.on_progress:
            return
        now = time.monotonic()
        if force or now - self._last >= PROGRESS_INTERVAL:
            self._last = now
            self.on_progress(self.files, self.bytes, current)


def _safe_size(path: str, on_error=None) -> int:
    """Taille d'un fichier ; 0 s'il est illisible — mais alors ``on_error`` est
    prévenu. Un fichier verrouillé (PST ouvert, antivirus en cours) compté comme
    vide sans le dire est une sous-évaluation silencieuse du volume du cas.
    """
    try:
        return os.path.getsize(path)
    except OSError as exc:
        if on_error:
            on_error(exc)
        return 0


def folder_size(path: str, on_progress=None, should_stop=None, on_error=None) -> int:
    """Somme récursive des tailles de fichiers d'un dossier.

    ``on_progress(fichiers, octets, chemin_en_cours)`` est appelé au fil de l'eau
    (cadencé, cf. ``PROGRESS_INTERVAL``). Si ``should_stop()`` devient vrai, le
    parcours s'arrête et renvoie le **total partiel** — à l'appelant de le
    rejeter (cf. contrat en tête de module).

    ``on_error(OSError)`` est appelé à chaque échec de lecture : dossier devenu
    illisible (il est passé à ``os.walk`` comme ``onerror``, **sans quoi
    l'erreur serait avalée sans trace**) comme fichier verrouillé. Le total
    rendu est alors incomplet, et l'appelant doit le rejeter au même titre
    qu'une mesure interrompue.
    """
    total = 0
    rep = _Reporter(on_progress)
    for root, _dirs, files in os.walk(path, onerror=on_error):
        if should_stop and should_stop():
            return total
        for name in files:
            if should_stop and should_stop():
                return total
            size = _safe_size(os.path.join(root, name), on_error)
            total += size
            rep.add(size, root)
    return total


def _image_segments(path: str, on_error=None) -> list[str]:
    """Chemins de tous les segments d'une image (ou le fichier seul).

    Les familles d'extensions viennent de ``image_families``, table partagée
    avec ``forensic_scan`` et ``path_parser``. Ce module en portait une copie
    incomplète (EWF, brut découpé et AD1 seulement) : une image LEF, SMART ou
    EWF v2 n'y matchait rien et seul son 1er segment était compté, ce qui
    sous-évaluait le volume du cas (corrigé le 18/09/2026).

    ⚠ **Radical et extension se comparent tous deux sans tenir compte de la
    casse.** Windows ne la distingue pas : un chemin collé ou tapé en
    « IMG.E01 » désigne bien le fichier « img.E01 » du disque, et
    ``os.path.exists`` le confirme. Comparer le radical à l'identique faisait
    alors échouer le rapprochement des segments, retomber sur le fichier seul
    et ne compter que le 1er tronçon — la même sous-évaluation que ci-dessus,
    par un autre déclencheur (audit du 18/09/2026, reproduit : 100 octets
    rendus au lieu de 350). L'extension, elle, était déjà abaissée ; c'est
    cette asymétrie qui a trahi l'oubli.
    """
    directory = os.path.dirname(path)
    stem, ext = os.path.splitext(os.path.basename(path))
    stem = stem.lower()

    motifs = image_families.segment_patterns(ext)
    if not motifs:
        return [path]

    try:
        entries = os.listdir(directory)
    except OSError as exc:
        if on_error:
            on_error(exc)
        return [path]
    segments = [os.path.join(directory, n) for n in entries
                if os.path.splitext(n)[0].lower() == stem
                and any(m.match(os.path.splitext(n)[1].lower()) for m in motifs)]
    return segments or [path]


def image_size(path: str, on_progress=None, should_stop=None, on_error=None) -> int:
    """Taille d'une image, en sommant TOUS les segments le cas échéant.

    Gère toutes les familles à segments de ``image_families`` (EWF et EWF v2,
    LEF, SMART, AD1, brut découpé) ; sinon taille du fichier unique.
    **Piège métier** : pointer le 1ᵉ segment doit rendre le total, pas la
    taille de ce seul fichier.

    ``on_error(OSError)`` signale un segment illisible ou un dossier devenu
    inaccessible : le total est alors incomplet, à rejeter par l'appelant.
    """
    if not os.path.exists(path):
        return 0
    total = 0
    rep = _Reporter(on_progress)
    for seg in _image_segments(path, on_error):
        if should_stop and should_stop():
            return total
        size = _safe_size(seg, on_error)
        total += size
        rep.add(size, seg)
    return total


def source_size(source, on_progress=None, should_stop=None, on_error=None) -> int:
    """Taille (octets) d'une ``Source`` selon son type."""
    return measure_path(source.path, source.source_type, on_progress, should_stop,
                        on_error)


def measure_path(path: str, source_type: str = None, on_progress=None,
                 should_stop=None, on_error=None) -> int:
    """Taille d'un chemin ; ``source_type`` force le traitement « image disque »."""
    if source_type == config.SOURCE_TYPE_DISK_IMAGE:
        return image_size(path, on_progress, should_stop, on_error)
    if os.path.isfile(path):
        return _safe_size(path, on_error)
    if os.path.isdir(path):
        return folder_size(path, on_progress, should_stop, on_error)
    return 0


def oversized_sources(sources, limit_bytes: int):
    """Sources dont la taille seule dépasse la limite (non fractionnables)."""
    return [s for s in sources if (s.size_bytes or 0) > limit_bytes]


# --- Moteur de mesure en lot (partagé Import / Inventaire) ----------------- #
def cache_key(path: str) -> str:
    """Clé de cache d'un chemin (même normalisation que ``case_info``)."""
    return path_parser.normalize_path(path).lower()


def measure_sources(items, out_queue, should_stop=None, cache=None):
    """Mesure une liste d'éléments et poste l'avancement dans ``out_queue``.

    ``items`` : liste de dicts ``{key, path, label, type}`` (``type`` = type de
    source ; ``key`` = identifiant rendu à l'appelant). ``cache`` : dict
    ``{clé normalisée: octets}`` de mesures déjà connues, réutilisées telles
    quelles.

    Messages postés :
      - ``("progress", i, total, label, fichiers, octets, secondes)``
      - ``("row", key, octets)`` — une mesure terminée
      - ``("done", results, cached_keys, cancelled, failed)`` — ``results`` =
        ``{key: octets}`` (mesures **complètes** uniquement), ``cached_keys`` =
        clés reprises du cache (donc déjà persistées, à ne pas réécrire),
        ``failed`` = clés dont la lecture a échoué, donc **non mesurées**.

    ``failed`` est le 5ᵉ élément, ajouté le 18/09/2026 : les appelants qui
    dépaquettent les trois premiers continuent de fonctionner sans changement.

    À exécuter dans un thread : la file est drainée par l'UI. Ne lève pas.
    """
    results, cached_keys, cancelled = {}, set(), False
    failed: set = set()
    total = len(items)
    started = time.monotonic()
    cache = cache or {}

    for i, item in enumerate(items, start=1):
        if should_stop and should_stop():
            cancelled = True
            break
        label = item.get("label") or item["path"]
        out_queue.put(("progress", i, total, label, 0, 0, time.monotonic() - started))

        cached = cache.get(cache_key(item["path"]))
        if cached is not None:
            size = int(cached)
            cached_keys.add(item["key"])
        else:
            def on_progress(files, nbytes, _current, _i=i, _label=label):
                out_queue.put(("progress", _i, total, _label, files, nbytes,
                               time.monotonic() - started))
            # Un seul échec de lecture suffit à rendre le total faux : on ne
            # compte pas les erreurs, on retient qu'il y en a eu.
            illisible = []
            size = measure_path(item["path"], item.get("type"), on_progress,
                                should_stop, lambda _exc: illisible.append(1))
            # Interruption pendant CETTE source : sa taille est partielle → on la
            # jette (cf. contrat en tête de module).
            if should_stop and should_stop():
                cancelled = True
                break
            # Lecture partielle (partage déconnecté, dossier ou fichier
            # illisible) : même verdict que l'interruption — la source n'est pas
            # enregistrée et reste « à mesurer ». Les autres continuent.
            if illisible:
                failed.add(item["key"])
                continue
        results[item["key"]] = size
        out_queue.put(("row", item["key"], size))

    out_queue.put(("done", results, cached_keys, cancelled, failed))
