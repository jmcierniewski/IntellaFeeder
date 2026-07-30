"""Garde-fou : les fallbacks FR écrits en dur doivent suivre ``lang/FR.lang``.

Chaque appel ``i18n.t("clé", "texte FR")`` porte le français en dur comme valeur
de repli (langue socle, cf. ``i18n``). Ces textes ne s'affichent que si une clé
manque — donc une divergence passe inaperçue jusqu'au jour où un ``.lang``
incomplet est livré et ressort une formulation abandonnée. Ce test l'interdit :
9 fallbacks avaient dérivé au renommage « Récapituler » → « Analyser les
chemins » (corrigés au lot 4).

Il vérifie aussi qu'aucun appel ne référence une clé absente de FR.lang
(faute de frappe dans la clé = texte jamais traduit).
"""

import ast
import io
import json
import os

import pytest

SCRIPT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
# Généré depuis les .lang : ses chaînes n'ont pas à être comparées à elles-mêmes.
IGNORES = {"lang_data.py"}


def _fr_strings():
    with io.open(os.path.join(SCRIPT_DIR, "lang", "FR.lang"), encoding="utf-8") as f:
        return json.load(f)["strings"]


def _calls():
    """Tous les ``i18n.t(clé_littérale, défaut_littéral)`` du code applicatif."""
    for name in sorted(os.listdir(SCRIPT_DIR)):
        if not name.endswith(".py") or name in IGNORES:
            continue
        path = os.path.join(SCRIPT_DIR, name)
        with io.open(path, encoding="utf-8") as f:
            tree = ast.parse(f.read(), filename=name)
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call) or len(node.args) < 2:
                continue
            func = node.func
            if not (isinstance(func, ast.Attribute) and func.attr == "t"
                    and isinstance(func.value, ast.Name) and func.value.id == "i18n"):
                continue
            key_node, def_node = node.args[0], node.args[1]
            if not (isinstance(key_node, ast.Constant) and isinstance(key_node.value, str)):
                continue
            try:
                default = ast.literal_eval(def_node)
            except (ValueError, SyntaxError):
                continue          # défaut calculé (rare) : hors périmètre
            if isinstance(default, str):
                yield name, node.lineno, key_node.value, default


def test_des_appels_sont_bien_detectes():
    """Sécurité du test lui-même : si l'extraction casse, il ne prouverait rien."""
    assert len(list(_calls())) > 100


def test_aucune_cle_inconnue():
    fr = _fr_strings()
    inconnues = [f"{n}:{l} {k}" for n, l, k, _d in _calls() if k not in fr]
    assert inconnues == [], "clés absentes de lang/FR.lang :\n" + "\n".join(inconnues)


def test_fallbacks_alignes_sur_le_fichier_fr():
    fr = _fr_strings()
    divergents = [f"{n}:{l} {k}\n   code : {d!r}\n   lang : {fr[k]!r}"
                  for n, l, k, d in _calls() if k in fr and fr[k] != d]
    assert divergents == [], "fallbacks FR périmés :\n" + "\n".join(divergents)
