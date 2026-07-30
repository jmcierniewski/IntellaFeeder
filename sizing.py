"""Calcul de la taille des sources : mesure unitaire + moteur de mesure en lot.

Deux niveaux :

1. **Mesure unitaire** — ``folder_size`` / ``image_size`` / ``source_size``.
   Chacune accepte ``on_progress`` (retour au fil de l'eau) et ``should_stop``
   (interruption). Sur un NAS, un dossier peut demander des dizaines de minutes :
   sans ces deux crochets, l'utilisateur n'a ni visibilité ni sortie de secours.
2. **Moteur en lot** — ``measure_sources`` : parcourt une liste d'éléments, gère
   le cache, la progression et l'annulation, et poste tout dans une ``queue``.
   Partagé par l'onglet Import (nouvelles sources) et l'onglet Inventaire
   (dossiers à 0). Ce module ne touche à AUCUN widget : c'est l'appelant qui
   draine la file sur le thread UI (tkinter n'est pas thread-safe).

⚠ Sémantique d'annulation (contrat) : une source **interrompue en cours de
mesure n'est jamais enregistrée** — seules les mesures complètes sont rendues.
Une taille partielle ferait passer une source volumineuse sous la limite du cas.
"""

import os
import re
import time

import config
import path_parser

_RE_EWF = re.compile(r"\.e\d{2}$", re.IGNORECASE)   # .E01, .E02, ...
_RE_SPLIT_DD = re.compile(r"\.\d{3}$")              # .001, .002, ...
_RE_AD1 = re.compile(r"\.ad\d+$", re.IGNORECASE)    # .ad1, .ad2, ... .ad28

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


def _safe_size(path: str) -> int:
    try:
        return os.path.getsize(path)
    except OSError:
        return 0


def folder_size(path: str, on_progress=None, should_stop=None) -> int:
    """Somme récursive des tailles de fichiers d'un dossier.

    ``on_progress(fichiers, octets, chemin_en_cours)`` est appelé au fil de l'eau
    (cadencé, cf. ``PROGRESS_INTERVAL``). Si ``should_stop()`` devient vrai, le
    parcours s'arrête et renvoie le **total partiel** — à l'appelant de le
    rejeter (cf. contrat d'annulation en tête de module).
    """
    total = 0
    rep = _Reporter(on_progress)
    for root, _dirs, files in os.walk(path):
        if should_stop and should_stop():
            return total
        for name in files:
            if should_stop and should_stop():
                return total
            size = _safe_size(os.path.join(root, name))
            total += size
            rep.add(size, root)
    return total


def _image_segments(path: str) -> list[str]:
    """Chemins de tous les segments d'une image (ou le fichier seul)."""
    directory = os.path.dirname(path)
    stem, ext = os.path.splitext(os.path.basename(path))

    pattern = None
    if _RE_EWF.fullmatch(ext):
        pattern = _RE_EWF
    elif _RE_SPLIT_DD.fullmatch(ext):
        pattern = _RE_SPLIT_DD
    elif _RE_AD1.fullmatch(ext):
        pattern = _RE_AD1
    if pattern is None:
        return [path]

    try:
        entries = os.listdir(directory)
    except OSError:
        return [path]
    segments = [os.path.join(directory, n) for n in entries
                if os.path.splitext(n)[0] == stem and pattern.fullmatch(os.path.splitext(n)[1])]
    return segments or [path]


def image_size(path: str, on_progress=None, should_stop=None) -> int:
    """Taille d'une image, en sommant TOUS les segments le cas échéant.

    Gère EWF (.E01, .E02, …), split dd (.001, .002, …) et AD1 ; sinon taille du
    fichier unique. **Piège métier** : pointer le 1ᵉ segment doit rendre le
    total, pas la taille de ce seul fichier.
    """
    if not os.path.exists(path):
        return 0
    total = 0
    rep = _Reporter(on_progress)
    for seg in _image_segments(path):
        if should_stop and should_stop():
            return total
        size = _safe_size(seg)
        total += size
        rep.add(size, seg)
    return total


def source_size(source, on_progress=None, should_stop=None) -> int:
    """Taille (octets) d'une ``Source`` selon son type."""
    return measure_path(source.path, source.source_type, on_progress, should_stop)


def measure_path(path: str, source_type: str = None, on_progress=None, should_stop=None) -> int:
    """Taille d'un chemin ; ``source_type`` force le traitement « image disque »."""
    if source_type == config.SOURCE_TYPE_DISK_IMAGE:
        return image_size(path, on_progress, should_stop)
    if os.path.isfile(path):
        return _safe_size(path)
    if os.path.isdir(path):
        return folder_size(path, on_progress, should_stop)
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
      - ``("done", results, cached_keys, cancelled)`` — ``results`` =
        ``{key: octets}`` (mesures **complètes** uniquement), ``cached_keys`` =
        clés reprises du cache (donc déjà persistées, à ne pas réécrire).

    À exécuter dans un thread : la file est drainée par l'UI. Ne lève pas.
    """
    results, cached_keys, cancelled = {}, set(), False
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
            size = measure_path(item["path"], item.get("type"), on_progress, should_stop)
            # Interruption pendant CETTE source : sa taille est partielle → on la
            # jette (cf. contrat d'annulation).
            if should_stop and should_stop():
                cancelled = True
                break
        results[item["key"]] = size
        out_queue.put(("row", item["key"], size))

    out_queue.put(("done", results, cached_keys, cancelled))
