"""Glisser-déposer de fichiers depuis l'Explorateur, sans dépendance externe.

Tkinter ne sait pas recevoir un drop de l'Explorateur : il faut passer par
Windows. Le choix (07/09/2026) a été de le faire en **ctypes** plutôt qu'avec
``tkinterdnd2``, pour ne pas casser le contrat du projet — bibliothèque standard
seule, exe autonome, rien à embarquer en plus au packaging.

Mécanique, volontairement minimale :

1. ``DragAcceptFiles(hwnd, TRUE)`` déclare le widget preneur de fichiers ;
2. sa procédure de fenêtre est **sous-classée** pour intercepter ``WM_DROPFILES``
   et lire les chemins déposés (``DragQueryFileW``), tout le reste étant
   retransmis à la procédure d'origine ;
3. la procédure de fenêtre **ne touche à rien de Tk** : elle dépose les chemins
   dans une ``queue.Queue`` et rend la main. Une boucle ``after`` côté interface
   les consomme et appelle le callback.

Trois précautions sans lesquelles ça plante — la première a coûté un crash en
production le 07/09/2026 :

- **aucun appel Tcl/Tk depuis la procédure de fenêtre.** Un vrai dépôt arrive
  *pendant* que Tk traite ses messages (``Tcl_DoOneEvent`` → ``DispatchMessage``
  → notre procédure) : y appeler ``widget.after()``, c'est réentrer dans
  l'interpréteur Tcl, et l'application se ferme **sans trace ni exception**.
  ⚠ Un test qui poste le message avec ``SendMessage`` depuis du code Python ne
  reproduit PAS ce contexte (aucune réentrance) et passe au vert : il faut un
  ``PostMessage`` depuis un autre thread, boucle Tk en marche.
- la fonction de rappel ctypes est **gardée en référence** dans ``_HOOKS`` ;
  ramassée par le GC, Windows appellerait une adresse libérée ;
- la procédure d'origine est **restaurée** à la destruction du widget.

Hors Windows, ou si l'API refuse, ``accept_files`` retourne ``False`` : l'appel
est sans effet et l'application fonctionne comme avant (les panneaux restent
remplissables au collage et par le bouton « Ajouter un dossier… »).
"""

import queue
import sys

WM_DROPFILES = 0x0233
# Cadence de relève de la file de dépôts (ms). Assez court pour que le dépôt
# paraisse immédiat, assez long pour ne rien coûter au repos.
POLL_MS = 120
GWLP_WNDPROC = -4
_MAX_PATH = 32767          # chemin long Unicode

# widget id -> (hwnd, ancienne procédure, rappel ctypes) — voir docstring.
_HOOKS: dict = {}

_available = sys.platform == "win32"
if _available:
    import ctypes
    from ctypes import wintypes

    try:
        _user32 = ctypes.WinDLL("user32", use_last_error=True)
        _shell32 = ctypes.WinDLL("shell32", use_last_error=True)

        LRESULT = ctypes.c_ssize_t
        _WNDPROC = ctypes.WINFUNCTYPE(LRESULT, wintypes.HWND, wintypes.UINT,
                                      wintypes.WPARAM, wintypes.LPARAM)

        # SetWindowLongPtrW n'existe qu'en 64 bits ; en 32 bits c'est
        # SetWindowLongW qui porte le même rôle.
        _set_proc = getattr(_user32, "SetWindowLongPtrW", None) or _user32.SetWindowLongW
        _get_proc = getattr(_user32, "GetWindowLongPtrW", None) or _user32.GetWindowLongW
        _set_proc.restype = LRESULT
        _set_proc.argtypes = [wintypes.HWND, ctypes.c_int, LRESULT]
        _get_proc.restype = LRESULT
        _get_proc.argtypes = [wintypes.HWND, ctypes.c_int]

        _call_proc = _user32.CallWindowProcW
        _call_proc.restype = LRESULT
        _call_proc.argtypes = [LRESULT, wintypes.HWND, wintypes.UINT,
                               wintypes.WPARAM, wintypes.LPARAM]

        _shell32.DragAcceptFiles.argtypes = [wintypes.HWND, wintypes.BOOL]
        _shell32.DragQueryFileW.restype = wintypes.UINT
        _shell32.DragQueryFileW.argtypes = [wintypes.HANDLE, wintypes.UINT,
                                            wintypes.LPWSTR, wintypes.UINT]
        _shell32.DragFinish.argtypes = [wintypes.HANDLE]
    except (OSError, AttributeError):       # pragma: no cover — API indisponible
        _available = False


def is_available() -> bool:
    """Le glisser-déposer est-il utilisable sur ce poste ?"""
    return _available


def _dropped_paths(hdrop) -> list:
    """Chemins portés par un HDROP (Unicode, chemins longs compris)."""
    count = _shell32.DragQueryFileW(hdrop, 0xFFFFFFFF, None, 0)
    out = []
    for i in range(count):
        length = _shell32.DragQueryFileW(hdrop, i, None, 0)
        if not length:
            continue
        buf = ctypes.create_unicode_buffer(min(length + 1, _MAX_PATH))
        if _shell32.DragQueryFileW(hdrop, i, buf, len(buf)):
            out.append(buf.value)
    return out


def accept_files(widget, callback) -> bool:
    """Fait accepter à ``widget`` les fichiers lâchés depuis l'Explorateur.

    ``callback(chemins)`` reçoit une liste de chemins absolus, sur le thread de
    l'interface, hors de tout traitement de message Windows (cf. docstring du
    module : la procédure de fenêtre ne fait que remplir une file). Retourne
    ``False`` si le glisser-déposer n'est pas disponible (autre système, API
    refusée) ou si le widget est déjà branché.
    """
    if not _available:
        return False
    key = str(widget)
    if key in _HOOKS:
        return True
    try:
        hwnd = wintypes.HWND(widget.winfo_id())
    except Exception:                       # pragma: no cover — widget non réalisé
        return False

    ancien = _get_proc(hwnd, GWLP_WNDPROC)
    if not ancien:                          # pragma: no cover
        return False

    file = queue.Queue()

    def _proc(h, msg, wparam, lparam):
        # ⚠ Zone interdite à Tk : ni `after`, ni `event_generate`, ni le moindre
        # appel Tcl — on est dans la pile de Tk, y réentrer ferme l'application
        # sans trace. Ici : lire, mettre en file, rendre la main. Rien d'autre.
        if msg == WM_DROPFILES:
            try:
                try:
                    chemins = _dropped_paths(wparam)
                finally:
                    _shell32.DragFinish(wparam)
                if chemins:
                    file.put(chemins)
            except Exception:               # noqa: S110 — pragma: no cover, jamais vers Windows
                pass
            return 0
        return _call_proc(ancien, h, msg, wparam, lparam)

    rappel = _WNDPROC(_proc)
    adresse = ctypes.cast(rappel, ctypes.c_void_p).value
    if not _set_proc(hwnd, GWLP_WNDPROC, adresse):
        # SetWindowLongPtr renvoie 0 aussi bien sur erreur que si l'ancienne
        # valeur était nulle ; ici `ancien` est non nul, donc 0 = échec.
        return False
    _shell32.DragAcceptFiles(hwnd, True)
    _HOOKS[key] = (hwnd, ancien, rappel)

    def _pump():
        """Relève la file depuis la boucle Tk — le seul endroit où appeler Tk."""
        if key not in _HOOKS:
            return                          # widget détruit : plus de relance
        try:
            lots = []
            try:
                while True:
                    lots.append(file.get_nowait())
            except queue.Empty:
                pass
            for chemins in lots:
                callback(chemins)
        finally:
            # Relance garantie : une exception du callback (dialogue fermé de
            # travers, chemin illisible) ne doit pas éteindre le dépôt pour le
            # reste de la session.
            widget.after(POLL_MS, _pump)

    widget.after(POLL_MS, _pump)
    widget.bind("<Destroy>", lambda e, k=key: _release(k), add="+")
    return True


def _release(key):
    """Rend la procédure d'origine (idempotent : <Destroy> peut être multiple)."""
    entry = _HOOKS.pop(key, None)
    if not entry:
        return
    hwnd, ancien, _rappel = entry
    try:
        _shell32.DragAcceptFiles(hwnd, False)
        _set_proc(hwnd, GWLP_WNDPROC, ancien)
    except Exception:                       # noqa: S110 — pragma: no cover, fenêtre déjà morte
        pass
