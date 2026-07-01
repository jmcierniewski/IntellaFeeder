"""Persistance des préférences dans un fichier .ini (chemin IntellaCmd, etc.).

Le fichier est placé à côté de l'exe/script s'il est inscriptible (portable),
sinon dans %APPDATA%\\<APP_NAME>\\.
"""

import configparser
import os

import config

_SECTION = "general"


def _ini_path() -> str:
    base = config.base_dir()
    if _is_writable(base):
        return os.path.join(base, config.INI_NAME)
    appdata = os.environ.get("APPDATA") or base
    folder = os.path.join(appdata, config.APP_NAME)
    try:
        os.makedirs(folder, exist_ok=True)
    except OSError:
        folder = base
    return os.path.join(folder, config.INI_NAME)


def _is_writable(folder: str) -> bool:
    test = os.path.join(folder, ".write_test.tmp")
    try:
        with open(test, "w", encoding="utf-8") as f:
            f.write("x")
        os.remove(test)
        return True
    except OSError:
        return False


class Settings:
    """Lecture/écriture des préférences (section unique ``general``)."""

    def __init__(self):
        self.path = _ini_path()
        # interpolation=None : les valeurs peuvent contenir « % » (ex. arguments
        # supplémentaires, chemins) sans déclencher l'interpolation configparser.
        self.parser = configparser.ConfigParser(interpolation=None)
        if os.path.isfile(self.path):
            try:
                self.parser.read(self.path, encoding="utf-8")
            except (OSError, configparser.Error):
                pass
        if not self.parser.has_section(_SECTION):
            self.parser.add_section(_SECTION)

    def get(self, key: str, default: str = "") -> str:
        return self.parser.get(_SECTION, key, fallback=default)

    def set(self, key: str, value: str) -> None:
        self.parser.set(_SECTION, key, value or "")

    def save(self) -> None:
        try:
            with open(self.path, "w", encoding="utf-8") as f:
                self.parser.write(f)
        except OSError:
            pass
