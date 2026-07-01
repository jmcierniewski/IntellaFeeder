"""Profils de paramètres d'analyse : **un fichier JSON par profil** dans
``base\\profils`` (partagé entre tous les cas).

Format d'un fichier ``profils\\<nom assaini>.json`` ::

    {"name": "<nom réel>", "options": {<clé_option>: <valeur>, ...}}

Seules les options **différentes du défaut** sont stockées (profil compact, cf.
``profile_catalog.diff_from_default``). Le profil ``défaut`` est **réservé et non
modifiable** : il n'a pas de fichier ; il représente l'absence d'options.

Choix du stockage (fichier vs ``.ini``) : 1 fichier par profil = partage,
sauvegarde et édition à l'unité, pas de ``.ini`` qui gonfle. JSON (et non XML) car
c'est le format natif de ``-addSourcesFromJson`` → aucune re-traduction.
"""

import json
import os

import config
import i18n
import profile_catalog

DEFAULT_NAME = "défaut"


def _dir() -> str:
    d = config.profiles_dir()
    try:
        os.makedirs(d, exist_ok=True)
    except OSError:
        pass
    return d


def _file_for(name: str) -> str:
    return os.path.join(_dir(), config.sanitize_filename(name) + ".json")


def _load_file(path: str):
    """Retourne ``{name, options, comment}`` ou ``None`` si illisible."""
    try:
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
    except (OSError, ValueError):
        return None
    if not isinstance(data, dict):
        return None
    name = (data.get("name") or "").strip()
    opts = data.get("options")
    if not name or not isinstance(opts, dict):
        return None
    return {"name": name, "options": opts, "comment": data.get("comment") or ""}


def _all() -> dict:
    """{nom: record} de tous les profils sur disque (hors ``défaut``).

    ``record`` = ``{"options": {...}, "comment": "..."}``."""
    out = {}
    try:
        files = [f for f in os.listdir(_dir()) if f.lower().endswith(".json")]
    except OSError:
        return out
    for f in files:
        rec = _load_file(os.path.join(_dir(), f))
        if rec and rec["name"] != DEFAULT_NAME:
            out[rec["name"]] = {"options": rec["options"], "comment": rec["comment"]}
    return out


def list_names() -> list[str]:
    """``défaut`` en tête, puis les profils triés (insensible à la casse)."""
    return [DEFAULT_NAME] + sorted(_all().keys(), key=str.lower)


def exists(name: str) -> bool:
    return name == DEFAULT_NAME or name in _all()


def get_values(name: str) -> dict:
    """Valeurs complètes d'un profil = défauts du catalogue + options stockées.

    ``défaut`` (ou inconnu) → snapshot vierge (tous les défauts)."""
    values = profile_catalog.default_values()
    if name and name != DEFAULT_NAME:
        for k, v in _all().get(name, {}).get("options", {}).items():
            if k in values:
                values[k] = profile_catalog.coerce(k, v)
    return values


def get_comment(name: str) -> str:
    """Commentaire libre associé au profil (vide pour ``défaut``/inconnu)."""
    if not name or name == DEFAULT_NAME:
        return ""
    return _all().get(name, {}).get("comment", "")


def save_profile(name: str, values: dict, comment: str = "") -> None:
    """Crée ou met à jour un profil (1 fichier). Lève ``ValueError`` si nom vide
    ou « défaut »."""
    name = (name or "").strip()
    if not name:
        raise ValueError(i18n.t("profiles.err_name_empty", "Le nom du profil est vide."))
    if name == DEFAULT_NAME:
        raise ValueError(i18n.t("profiles.err_default_reserved",
                                "Le profil « défaut » est réservé et non modifiable."))
    payload = {"name": name, "comment": comment or "",
               "options": profile_catalog.diff_from_default(values)}
    with open(_file_for(name), "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)


def delete_profile(name: str) -> None:
    if name == DEFAULT_NAME:
        raise ValueError(i18n.t("profiles.err_default_no_delete",
                                "Le profil « défaut » ne peut pas être supprimé."))
    try:
        os.remove(_file_for(name))
    except OSError:
        pass


def rename_profile(old: str, new: str) -> None:
    new = (new or "").strip()
    if old == DEFAULT_NAME or new == DEFAULT_NAME:
        raise ValueError(i18n.t("profiles.err_default_reserved_short", "Le profil « défaut » est réservé."))
    if not new:
        raise ValueError(i18n.t("profiles.err_new_name_empty", "Le nouveau nom est vide."))
    profs = _all()
    if old not in profs:
        raise ValueError(i18n.t("profiles.err_not_found", "Profil introuvable : {n}", n=old))
    if new in profs:
        raise ValueError(i18n.t("profiles.err_already_exists", "Un profil « {n} » existe déjà.", n=new))
    save_profile(new, get_values(old), get_comment(old))
    delete_profile(old)


def emit_map(names) -> dict:
    """{nom: options_diff} pour un ensemble de noms (filtrage image fait à la
    génération, par source)."""
    out = {}
    for n in set(names):
        out[n] = {} if n == DEFAULT_NAME else profile_catalog.diff_from_default(get_values(n))
    return out
