# -*- coding: utf-8 -*-
"""Aucun module ne cite un nom que personne ne définit.

🐞 **Ce que ce test rattrape** (11/09/2026). En retirant ``show_mime_filter`` de
``ui_widgets``, la constante ``SETTING_STATUS_COLORS`` est partie avec lui —
mais deux lignes de ``show_source_settings`` continuaient de l'appeler. Résultat
à l'écran : « Voir les réglages de la source… » ouvrait une fenêtre de 940×600
**vide**, un ``NameError`` levé juste après son en-tête. Aucune alerte :
``py_compile`` ne regarde que la syntaxe, et la suite pytest ne couvre pas les
modules d'interface.

La lecture est volontairement **permissive** : on rassemble tous les noms liés
n'importe où dans le module (module, fonctions, classes, boucles, ``except…as``,
compréhensions) et l'on vérifie qu'aucune *lecture* ne porte sur autre chose.
Elle ne dira donc pas qu'une variable locale est lue dans une autre fonction —
mais elle dit, sans faux positif, qu'un nom a **disparu du fichier**.
"""

import ast
import builtins
import os

import pytest

SCRIPT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BUILTINS = set(dir(builtins)) | {"__file__", "__name__", "__doc__", "WindowsError"}


def _modules():
    for nom in sorted(os.listdir(SCRIPT_DIR)):
        if nom.endswith(".py") and not nom.startswith("_"):
            yield nom


def _noms_lies(arbre: ast.AST) -> set:
    """Tous les noms que le module lie, à n'importe quelle profondeur."""
    lies = set()
    for n in ast.walk(arbre):
        if isinstance(n, ast.Name) and isinstance(n.ctx, (ast.Store, ast.Del)):
            lies.add(n.id)
        elif isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            lies.add(n.name)
            args = getattr(n, "args", None)
            if args is not None:
                for a in (list(args.posonlyargs) + list(args.args)
                          + list(args.kwonlyargs)):
                    lies.add(a.arg)
                for a in (args.vararg, args.kwarg):
                    if a is not None:
                        lies.add(a.arg)
        elif isinstance(n, (ast.Import, ast.ImportFrom)):
            for alias in n.names:
                lies.add((alias.asname or alias.name).split(".")[0])
        elif isinstance(n, ast.ExceptHandler) and n.name:
            lies.add(n.name)
        elif isinstance(n, (ast.Global, ast.Nonlocal)):
            lies.update(n.names)
        elif isinstance(n, ast.Lambda):
            a = n.args
            for arg in (list(a.posonlyargs) + list(a.args) + list(a.kwonlyargs)):
                lies.add(arg.arg)
            for arg in (a.vararg, a.kwarg):
                if arg is not None:
                    lies.add(arg.arg)
        elif isinstance(n, ast.MatchAs) and n.name:
            lies.add(n.name)
        elif isinstance(n, ast.MatchStar) and n.name:
            lies.add(n.name)
    return lies


@pytest.mark.parametrize("module", list(_modules()))
def test_aucun_nom_orphelin(module):
    chemin = os.path.join(SCRIPT_DIR, module)
    with open(chemin, encoding="utf-8") as fh:
        arbre = ast.parse(fh.read(), filename=module)
    connus = _noms_lies(arbre) | BUILTINS
    orphelins = sorted({n.id for n in ast.walk(arbre)
                        if isinstance(n, ast.Name)
                        and isinstance(n.ctx, ast.Load)
                        and n.id not in connus})
    assert not orphelins, (
        "%s cite un ou des noms que rien ne definit : %s"
        % (module, ", ".join(orphelins)))
