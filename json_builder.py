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


def _strip_trailing(path: str) -> str:
    """Retire les séparateurs de fin (problème connu entre guillemets)."""
    return path.rstrip().rstrip("\\/")


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


def import_command(exe: str, user: str, case_path: str, case_name: str,
                   sources_json_path: str, extra_args: str = "") -> str:
    """Commande IntellaCmd d'ajout/indexation des sources d'un (sous-)cas."""
    cmd = f'"{exe}" -u "{user}" -c "{_strip_trailing(case_path)}"'
    if case_name.strip():
        cmd += f' -cn "{case_name.strip()}"'
    cmd += f' -addSourcesFromJson "{sources_json_path}"'
    if extra_args.strip():
        cmd += f" {extra_args.strip()}"
    return cmd


def import_one_command(exe: str, user: str, case_path: str, case_name: str,
                       sources_json_path: str, log_path: str,
                       extra_args: str = "") -> str:
    """Commande d'ajout d'UNE source, avec journalisation dans ``log_path``."""
    cmd = import_command(exe, user, case_path, case_name, sources_json_path, "")
    cmd += " -log INFO"
    if extra_args.strip():
        cmd += f" {extra_args.strip()}"
    cmd += f' > "{log_path}" 2>&1'
    return cmd


# Argument passé au .bat par l'application pour supprimer la pause finale.
# Un .bat lancé à la main (double-clic) ne le reçoit pas et garde sa pause.
BAT_AUTO_FLAG = "auto"


def _echo_safe(text: str) -> str:
    """Neutralise les caractères spéciaux cmd pour un ``echo``."""
    for ch in '&<>|^()%"':
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
