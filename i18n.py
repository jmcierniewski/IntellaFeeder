"""Internationalisation : fichiers de langue ``Script\\lang\\<CODE>.lang`` (JSON)
et/ou langues **intégrées** dans ``lang_data.BUILTIN`` (module .py).

Un fichier/enregistrement de langue contient :
- ``strings`` : dict ``{clé: texte}`` pour les libellés de l'interface.
- ``help`` : contenu complet de l'onglet Aide, même structure que l'ancien
  ``ui_help._CONTENT`` (liste de ``[style, texte]``).

Les identifiants techniques (types MIME, clés d'options JSON…) ne sont PAS
traduits — seul le texte qui les entoure l'est.

⚠ Limite tkinter assumée : les widgets déjà construits ont leur texte figé.
Changer de langue en cours de session est donc mémorisé dans le ``.ini``
(clé ``language``) et appliqué **au prochain démarrage** — pas de retraduction
à chaud (nécessiterait de reconstruire toute la fenêtre).

**Deux sources, priorité au fichier externe** : ``lang\\<CODE>.lang`` (s'il
existe) l'emporte toujours sur ``lang_data.BUILTIN[CODE]`` — pratique pour
corriger une traduction ou ajouter une langue sans reconstruire l'exe. Les
langues intégrées (FR, US) fonctionnent même sans dossier ``lang\\`` du tout
(PyInstaller embarque ``lang_data.py`` comme n'importe quel module source).

``BASE_LANGUAGE`` (« FR ») est en plus la langue **socle** : chaque appel
``i18n.t(clé, "texte FR")`` porte déjà le français en dur comme valeur par
défaut. FR reste donc **toujours proposée** dans le sélecteur, même si elle
n'est ni en fichier ni dans ``lang_data.BUILTIN`` — pas de risque de rester
bloqué sur une langue non désirée si un fichier est supprimé par erreur.
"""

import json
import os

import config
import lang_data

BASE_LANGUAGE = "FR"

_current_code = ""
_current = {"strings": {}, "help": []}


def available_languages() -> list[str]:
    """Codes des langues disponibles : fichiers ``lang\\*.lang`` + langues
    intégrées (``lang_data.BUILTIN``), triés. ``BASE_LANGUAGE`` est toujours
    incluse, même sans fichier ni entrée intégrée."""
    try:
        files = [f for f in os.listdir(config.lang_dir()) if f.lower().endswith(".lang")]
    except OSError:
        files = []
    codes = {os.path.splitext(f)[0] for f in files}
    codes |= set(lang_data.BUILTIN)
    codes.add(BASE_LANGUAGE)
    return sorted(codes)


def _path_for(code: str) -> str:
    return os.path.join(config.lang_dir(), f"{code}.lang")


def _read(code: str):
    """Fichier externe ``lang\\<code>.lang`` s'il existe (priorité — permet
    l'édition sans recompiler), sinon la version intégrée à l'exe."""
    try:
        with open(_path_for(code), encoding="utf-8") as f:
            data = json.load(f)
        if isinstance(data, dict):
            return {"strings": data.get("strings") or {}, "help": data.get("help") or []}
    except (OSError, ValueError):
        pass
    builtin = lang_data.BUILTIN.get(code)
    if builtin:
        return {"strings": builtin.get("strings") or {}, "help": builtin.get("help") or []}
    return None


def load(code: str) -> bool:
    """Charge ``code`` comme langue courante. Retourne True si applicable.

    ``BASE_LANGUAGE`` réussit toujours, même sans source (fichier ni intégrée) :
    dans ce cas on charge un dict vide, et ``t()``/``help_content()`` retombent
    sur les valeurs françaises en dur du code (déjà la langue socle). Chaque
    appel remplace intégralement la langue courante — pas de mélange avec une
    langue chargée précédemment dans le process (sinon un changement de langue
    en cours de session resterait pollué par la précédente)."""
    global _current_code, _current
    data = _read(code)
    if data is None:
        if code != BASE_LANGUAGE:
            return False
        data = {"strings": {}, "help": []}
    _current_code, _current = code, data
    return True


def current_code() -> str:
    return _current_code


def t(key: str, default: str = "", **kwargs) -> str:
    """Traduction de ``key`` dans la langue courante, sinon ``default``
    (le français en dur porté par chaque appel — c'est le vrai repli)."""
    text = _current["strings"].get(key) or default or key
    if kwargs:
        try:
            return text.format(**kwargs)
        except (KeyError, IndexError):
            return text
    return text


def help_content() -> list:
    """Contenu ``[style, texte]`` de l'onglet Aide pour la langue courante."""
    return _current.get("help") or []
