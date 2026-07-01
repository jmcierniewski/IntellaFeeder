"""Point d'entrée de l'application.

Génère les fichiers JSON (et le .bat) nécessaires à l'import automatique de
sources dans Vound Intella Investigator via IntellaCmd.exe -addSourcesFromJson.
"""

import tkinter as tk

from ui import MainWindow


def main():
    root = tk.Tk()
    MainWindow(root)
    root.mainloop()


if __name__ == "__main__":
    main()
