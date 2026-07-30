"""Configuration pytest : rend les modules de ``Script\\`` importables.

Les tests couvrent **uniquement les modules sans interface** (pas de tkinter,
pas d'IntellaCmd.exe, pas d'accès réseau) : ils doivent tourner en quelques
secondes sur n'importe quelle machine, y compris sans cas Intella disponible.
"""

import os
import sys

import pytest

SCRIPT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if SCRIPT_DIR not in sys.path:
    sys.path.insert(0, SCRIPT_DIR)


@pytest.fixture
def tmp_case(tmp_path):
    """Dossier de cas factice : (chemin, nom du cas)."""
    folder = tmp_path / "CasFactice"
    folder.mkdir()
    return str(folder), "Cas de test"


def make_file(path, size_bytes: int):
    """Crée un fichier de ``size_bytes`` octets (parents créés au besoin)."""
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "wb") as f:
        f.write(b"\0" * size_bytes)
    return path
