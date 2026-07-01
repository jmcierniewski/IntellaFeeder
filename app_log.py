"""Journal applicatif : opérations horodatées, observables et exportables."""

import config


class AppLog:
    """Collecte les lignes de journal et notifie d'éventuels observateurs.

    Les observateurs (ex. l'onglet Journal) reçoivent chaque nouvelle ligne ;
    à l'inscription, l'historique déjà présent leur est rejoué.
    """

    def __init__(self):
        self.lines: list[str] = []
        self._listeners: list = []

    def log(self, message: str, level: str = "INFO") -> None:
        line = f"[{config.now_str()}] {level:<5} {message}"
        self.lines.append(line)
        for cb in self._listeners:
            cb(line)

    def add_listener(self, callback) -> None:
        self._listeners.append(callback)
        for line in self.lines:  # rejoue l'historique
            callback(line)

    def clear(self) -> None:
        self.lines.clear()

    def export(self, path: str) -> None:
        with open(path, "w", encoding="utf-8") as f:
            f.write("\n".join(self.lines))
