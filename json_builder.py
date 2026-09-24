"""Construction des JSON de sources et du script .bat IntellaCmd.

Import **résilient** (v2.2) : un JSON par source et une commande IntellaCmd par
source dans le .bat, chacune journalisée à part — l'échec d'une source n'arrête
pas les autres. Les fonctions « tout en un » d'origine (un seul sources.json,
un .bat enchaînant les commandes) ont été retirées au lot 4 : plus appelées
depuis ce changement de modèle.
"""

import json
import os

import config
import path_parser


def build_single_source_json(source, timezone: str, taskfile,
                             output_dir: str, filename: str,
                             options: dict = None) -> str:
    """Écrit un sources.json ne contenant qu'UNE source (import résilient).

    ``taskfile`` : chemin du fichier de tâche pour cette source, ou None.
    ``options`` : options d'indexation du profil de la source (déjà filtrées :
    diff du défaut + retrait des clés réservées aux images). Fusionnées dans le
    JSON sans écraser les champs de base.

    Note : la non-vérification d'intégrité (``-validateDiskImage false``) est
    passée en **argument de ligne de commande** par le générateur (option CLI
    `-vdi`, manuel p.4), pas dans ce JSON (clé absente du schéma documenté).
    """
    output_dir = os.path.abspath(output_dir)
    obj = {
        "name": source.name,
        "evidencePath": source.path,
        "sourceType": source.source_type,
        "timezone": timezone,
    }
    _BASE = ("name", "evidencePath", "sourceType", "timezone")
    for k, v in (options or {}).items():
        if k not in _BASE:
            obj[k] = v
    if taskfile:
        obj["taskFile"] = taskfile
    path = os.path.join(output_dir, filename)
    with open(path, "w", encoding="utf-8") as f:
        json.dump({"sources": [obj]}, f, ensure_ascii=True, indent=2)
    return path


# 🔴 Les valeurs qui composent la commande ne sont PAS toutes saisies par
# l'opérateur : le nom du cas et l'utilisateur sont lus dans le `case.xml`, un
# fichier qui vit sur le partage (audit paranoid du 18/09/2026). Une ligne
# assemblée par concaténation laissait donc un `case.xml` piégé refermer la
# citation et enchaîner sa propre commande, exécutée au clic sur « Importer ».
# D'où deux règles, appliquées par `_q` à CHAQUE argument :
#   • toujours citer — entre guillemets, cmd.exe ne voit plus ni `&`, ni `|`,
#     ni `<`, ni `>`, ni `^` ; un nom de cas « Dupont & Fils » reste légitime ;
#   • doubler le `%` — sinon cmd le développe comme une variable AVANT
#     l'exécution, et le chemin transmis à IntellaCmd n'est plus celui du
#     fichier écrit (un scellé « Scellé %2024% » partait ainsi à l'import sous
#     un chemin inexistant, sans que rien ne le signale : IntellaCmd renvoie 0
#     même en échec).
# Restent deux caractères qu'aucune citation ne dompte : le guillemet lui-même
# (cmd compte les guillemets avant que CommandLineToArgvW ne lise `\"`) et le
# retour à la ligne, qui couperait la commande en deux. Ils sont REFUSÉS — la
# garde amont est dans `validation.collect`, celle-ci est le dernier verrou.
_UNQUOTABLE = '"\r\n'


def _q(arg: str) -> str:
    """Argument prêt à être écrit dans un .bat : cité, ``%`` doublé.

    ⚠ Le doublement du ``%`` ne vaut QUE dans un fichier .bat (là, ``%%`` donne
    un ``%`` littéral). Ne pas réutiliser cette fonction pour un appel direct.
    """
    arg = arg or ""
    if any(ch in arg for ch in _UNQUOTABLE):
        raise ValueError(
            "Caractère interdit dans la commande d'import (guillemet ou retour "
            f"à la ligne) : {arg!r}")
    return '"' + arg.replace("%", "%%") + '"'


def _extra(extra_args: str) -> str:
    """Champ « Arguments supplémentaires » : recopié VERBATIM.

    C'est un fragment de ligne de commande écrit par l'opérateur lui-même, qui
    peut légitimement y vouloir plusieurs arguments, des guillemets ou une
    variable d'environnement. Seul le retour à la ligne est refusé : il
    couperait la commande en deux dans le .bat.
    """
    txt = (extra_args or "").strip()
    if "\r" in txt or "\n" in txt:
        raise ValueError("Le champ « Arguments supplémentaires » ne doit pas "
                         "contenir de retour à la ligne.")
    return txt


def import_argv(exe: str, user: str, case_path: str, case_name: str,
                sources_json_path: str) -> list[str]:
    """Arguments (liste, non cités) de l'ajout des sources d'un (sous-)cas.

    ⚠ Le nettoyage du chemin du cas passe par ``path_parser.normalize_path``, et
    par lui seul : la version locale d'autrefois réduisait ``X:\\`` à ``X:``, qui
    désigne pour un processus Windows le **répertoire courant** du lecteur X et
    non sa racine — IntellaCmd aurait ciblé un autre dossier que celui affiché,
    en silence (audit paranoid du 18/09/2026).
    """
    argv = [exe, "-u", user, "-c", path_parser.normalize_path(case_path)]
    if case_name.strip():
        argv += ["-cn", case_name.strip()]
    argv += ["-addSourcesFromJson", sources_json_path]
    return argv


def import_command(exe: str, user: str, case_path: str, case_name: str,
                   sources_json_path: str, extra_args: str = "") -> str:
    """Commande IntellaCmd d'ajout/indexation des sources d'un (sous-)cas.

    Destinée à un .bat : chaque argument est cité et ses ``%`` doublés (`_q`).
    """
    cmd = " ".join(_q(a) for a in import_argv(
        exe, user, case_path, case_name, sources_json_path))
    extra = _extra(extra_args)
    if extra:
        cmd += f" {extra}"
    return cmd


def import_one_command(exe: str, user: str, case_path: str, case_name: str,
                       sources_json_path: str, log_path: str,
                       extra_args: str = "") -> str:
    """Commande d'ajout d'UNE source, avec journalisation dans ``log_path``."""
    cmd = import_command(exe, user, case_path, case_name, sources_json_path, "")
    cmd += " -log INFO"
    extra = _extra(extra_args)
    if extra:
        cmd += f" {extra}"
    cmd += f" > {_q(log_path)} 2>&1"
    return cmd


# Argument passé au .bat par l'application pour supprimer la pause finale.
# Un .bat lancé à la main (double-clic) ne le reçoit pas et garde sa pause.
BAT_AUTO_FLAG = "auto"


def _echo_safe(text: str) -> str:
    """Neutralise les caractères spéciaux cmd pour un ``echo``.

    Les retours à la ligne en font partie : un nom de source qui en contiendrait
    ajouterait des lignes au .bat, exécutées comme des commandes.
    """
    for ch in '&<>|^()%"\r\n':
        text = text.replace(ch, "_")
    return text


def write_resilient_bat(entries, output_dir: str, filename: str,
                        title: str = "import resilient") -> str:
    """Écrit un .bat où chaque source est une commande indépendante.

    ``entries`` : liste de ``(label, command)``. Le .bat poursuit après l'échec
    d'une source (pas de ``&&``) et affiche OK/ÉCHEC par source.
    """
    output_dir = os.path.abspath(output_dir)
    total = len(entries)
    lines = ["@echo off", "chcp 65001 >nul",
             f"rem Genere par {config.APP_NAME} - {title}", "",
             "setlocal", ""]
    for i, (label, cmd) in enumerate(entries, start=1):
        lines.append(f"echo [{i}/{total}] {_echo_safe(label)}")
        lines.append(cmd)
        lines.append('if errorlevel 1 (echo    [ECHEC] code %errorlevel%) else (echo    [OK])')
        lines.append("")
    # 🐞 Le « Appuyez sur une touche… » BLOQUAIT « Lancer l'import complet »
    # (rapporté le 10/09/2026) : la fenêtre restait ouverte à attendre un clic,
    # donc `_poll_import` ne voyait jamais le processus finir et la validation
    # n'arrivait qu'après intervention. Mais le retirer tout court ferait
    # disparaître la console avant qu'on ait pu lire le bilan quand le .bat est
    # **double-cliqué depuis l'Explorateur** — un usage prévu par le contrat.
    # D'où la pause CONDITIONNELLE : l'application passe l'argument `auto`,
    # l'Explorateur n'en passe aucun.
    lines += ["echo.", "echo Termine.",
              f'if /i not "%~1"=="{BAT_AUTO_FLAG}" pause']

    path = os.path.join(output_dir, filename)
    with open(path, "w", encoding="utf-8", newline="\r\n") as f:
        f.write("\n".join(lines))
    return path
