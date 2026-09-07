r"""Fumée du glisser-déposer dans le VRAI contexte de délivrance du message.

La fumée précédente postait WM_DROPFILES avec SendMessage depuis du code Python :
aucune réentrance dans Tcl, donc elle passait au vert alors que l'application
se fermait brutalement au premier dépôt réel.

Ici le message est posté avec PostMessageW **depuis un autre thread**, la boucle
Tk tournant : Windows le délivre depuis `Tcl_DoOneEvent` → `DispatchMessage`,
exactement comme l'Explorateur. C'est ce contexte-là qui plante si la procédure
de fenêtre touche à Tk.

    python tests\manuel_fumee_dnd_reel.py            # doit finir « OK »
    python tests\manuel_fumee_dnd_reel.py --legacy   # réinstalle la faute :
                                                     # doit se fermer brutalement

Script de fumée MANUEL (préfixe `manuel_` : pytest ne le collecte pas — il ouvre
une fenêtre et ne peut pas tourner dans la suite automatique).
"""

import ctypes
import io
import os
import shutil
import sys
import tempfile
import threading
import tkinter as tk
from ctypes import wintypes

# Racine du code (ce fichier est dans Script/tests/) — jamais de chemin en dur :
# le dépôt est public.
SCRIPT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, SCRIPT)

GMEM_MOVEABLE, GMEM_ZEROINIT = 0x0002, 0x0040
WM_DROPFILES = 0x0233
LEGACY = "--legacy" in sys.argv


class DROPFILES(ctypes.Structure):
    _fields_ = [("pFiles", wintypes.DWORD), ("pt", wintypes.POINT),
                ("fNC", wintypes.BOOL), ("fWide", wintypes.BOOL)]


def post_drop(hwnd_value, paths):
    """Poste un WM_DROPFILES depuis CE thread (appelé depuis un thread annexe)."""
    k32, u32 = ctypes.WinDLL("kernel32"), ctypes.WinDLL("user32")
    k32.GlobalAlloc.restype = wintypes.HGLOBAL
    k32.GlobalAlloc.argtypes = [wintypes.UINT, ctypes.c_size_t]
    k32.GlobalLock.restype = ctypes.c_void_p
    k32.GlobalLock.argtypes = [wintypes.HGLOBAL]
    k32.GlobalUnlock.argtypes = [wintypes.HGLOBAL]
    u32.PostMessageW.argtypes = [wintypes.HWND, wintypes.UINT,
                                 ctypes.c_size_t, ctypes.c_ssize_t]
    data = ("".join(p + "\0" for p in paths) + "\0").encode("utf-16-le")
    h = k32.GlobalAlloc(GMEM_MOVEABLE | GMEM_ZEROINIT,
                        ctypes.sizeof(DROPFILES) + len(data))
    ptr = k32.GlobalLock(h)
    df = DROPFILES.from_address(ptr)
    df.pFiles = ctypes.sizeof(DROPFILES)
    df.fWide = True
    ctypes.memmove(ptr + ctypes.sizeof(DROPFILES), data, len(data))
    k32.GlobalUnlock(h)
    # PostMessage : asynchrone. Le message sera délivré par la boucle Tk.
    u32.PostMessageW(wintypes.HWND(hwnd_value), WM_DROPFILES, h, 0)


def install_legacy(dnd, widget, callback):
    """Réinstalle la faute d'origine : appel Tk depuis la procédure de fenêtre."""
    hwnd = wintypes.HWND(widget.winfo_id())
    ancien = dnd._get_proc(hwnd, dnd.GWLP_WNDPROC)

    def _proc(h, msg, wparam, lparam):
        if msg == WM_DROPFILES:
            try:
                chemins = dnd._dropped_paths(wparam)
            finally:
                dnd._shell32.DragFinish(wparam)
            if chemins:
                widget.after(0, lambda: callback(chemins))   # ← la faute
            return 0
        return dnd._call_proc(ancien, h, msg, wparam, lparam)

    rappel = dnd._WNDPROC(_proc)
    dnd._set_proc(hwnd, dnd.GWLP_WNDPROC,
                  ctypes.cast(rappel, ctypes.c_void_p).value)
    dnd._shell32.DragAcceptFiles(hwnd, True)
    dnd._HOOKS[str(widget)] = (hwnd, ancien, rappel)


def main():
    import dnd_windows
    import ui_import
    from ui import MainWindow

    ini = os.path.join(SCRIPT, "intellafeeder.ini")
    backup = ini + ".fumee_bak"
    if os.path.isfile(ini):
        shutil.copyfile(ini, backup)

    tmp = tempfile.mkdtemp(prefix="fumee_reel_")
    os.makedirs(os.path.join(tmp, "SCELLES"), exist_ok=True)
    for n in ("A.ad1", "A.ad2", "note.txt"):
        with io.open(os.path.join(tmp, "SCELLES", n), "w", encoding="utf-8") as f:
            f.write("x")

    if LEGACY:
        dnd_windows.accept_files = lambda w, cb: (install_legacy(dnd_windows, w, cb)
                                                  or True)

    root = tk.Tk()
    app = MainWindow(root)
    tab = app.import_tab
    app.notebook.select(tab)
    popups = []
    for nom in ("showinfo", "showwarning", "showerror"):
        setattr(ui_import.messagebox, nom, lambda t, m, **k: popups.append((t, m)))
    root.update()

    hwnd_images = tab.txt_images.winfo_id()
    hwnd_folders = tab.txt_folders.winfo_id()
    resultat = {}

    def poster():
        """Thread annexe : la boucle Tk tourne pendant ce temps."""
        post_drop(hwnd_images, [os.path.join(tmp, "SCELLES")])
        post_drop(hwnd_folders, [tmp])

    def verifier():
        images = [l for l in tab.txt_images.get("1.0", "end").splitlines() if l.strip()]
        dossiers = [l for l in tab.txt_folders.get("1.0", "end").splitlines() if l.strip()]
        resultat["images"] = [os.path.basename(p) for p in images]
        resultat["dossiers"] = dossiers
        root.destroy()

    root.after(600, lambda: threading.Thread(target=poster, daemon=True).start())
    root.after(5000, verifier)
    root.mainloop()

    if os.path.isfile(backup):
        shutil.copyfile(backup, ini)
        os.remove(backup)
    shutil.rmtree(tmp, ignore_errors=True)

    attendu_images = ["A.ad1"]
    ok = (resultat.get("images") == attendu_images
          and len(resultat.get("dossiers") or []) == 1)
    print("mode :", "LEGACY (faute d'origine)" if LEGACY else "code courant")
    print("images :", resultat.get("images"), "attendu", attendu_images)
    print("dossiers :", resultat.get("dossiers"))
    print("FUMEE :", "OK" if ok else "ECHEC")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
