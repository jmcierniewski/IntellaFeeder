"""Orchestration de la génération.

Sortie dans ``Script\\Cas\\<nom du cas>\\`` : sous-dossier ``scripts`` (JSON par
source + fichiers de tâches + .bat) et ``logs`` (journaux d'import).

Import **résilient** : une commande IntellaCmd ``-addSourcesFromJson`` par source,
chacune journalisée → l'échec d'une source n'interrompt pas les autres.

Garde-fou : volume déjà occupé (``case.xml/size`` via ``existing_bytes``) +
nouvelles sources vs limite. **Pas de cas compound automatique** : en cas de
dépassement, on se contente d'AVERTIR (``over_limit``) — la création d'un
sous-cas est faite manuellement par l'utilisateur, qui réimporte ensuite le
reste des sources en le ciblant.
"""

import os

import config
import json_builder
import profile_catalog
import sizing
import task_builder


def _combo_of(source, available_ids):
    """Combinaison effective de tâches d'une source (ids valides uniquement)."""
    return frozenset(source.selected_task_ids & available_ids)


def generate(sources, params, tasks, log) -> dict:
    """Génère les JSON par source + un .bat résilient mono-cas.

    ``params`` : user, case (dossier du cas, NAS), casename, exe, tz, extra,
    limit_gb, existing_bytes. **Pas de compound** : si le total dépasse la
    limite, le rapport porte ``over_limit`` (avertissement) — l'utilisateur crée
    un sous-cas manuellement et réimporte le reste en le ciblant.
    """
    user, exe, tz, extra = params["user"], params["exe"], params["tz"], params["extra"]
    # Non-vérification d'intégrité : portée par le champ « Arguments suppl. »
    # (`-validateDiskImage false`), pas ici — voir ui_import._sync_integrity_arg.
    # {nom_profil: options_diff} (sans filtrage image ; filtré par source ci-dessous).
    profile_options = params.get("profile_options", {}) or {}
    case = params["case"].rstrip().rstrip("\\/")
    case_name = params["casename"].strip() or os.path.basename(case) or "Case"
    safe = config.sanitize_filename(case_name)
    # Limite en octets (float) : ne PAS tronquer par int() — une limite
    # fractionnaire (ex. 0.260 Go pour un test) doit rester effective.
    limit = max(0.0, float(params["limit_gb"])) * config.GB

    scripts_dir = config.case_scripts_dir(case_name)
    logs_dir = config.case_logs_dir(case_name)
    # Logs scopés par run : sous-dossier horodaté (yyyyMMdd_HHmm). La validation
    # lit le run le plus récent → pas de mélange entre deux générations/imports.
    run_id = config.now_compact()
    run_logs_dir = os.path.join(logs_dir, run_id)
    os.makedirs(scripts_dir, exist_ok=True)
    os.makedirs(run_logs_dir, exist_ok=True)

    # Fichiers de tâches : un par combinaison réellement utilisée (dans scripts/).
    available_ids = {t["id"] for t in tasks}
    combos = {c for c in (_combo_of(s, available_ids) for s in sources) if c}
    taskfile_map = task_builder.build_combo_files(tasks, combos, scripts_dir)

    def taskfile_for(source):
        return taskfile_map.get(_combo_of(source, available_ids))

    total = sum((s.size_bytes or 0) for s in sources)
    existing = max(0, int(params.get("existing_bytes", 0) or 0))
    effective = existing + total
    produced = list(taskfile_map.values())

    def emit_source(loc, sub_name, prefix, idx, source):
        """Écrit le JSON d'une source et retourne ``(label, commande)``."""
        base = f"{safe}_{prefix}{idx:02d}_{config.sanitize_filename(source.name)}"
        # Options du profil de la source : retirer les clés réservées aux images
        # quand la source est un dossier/fichier.
        opts = dict(profile_options.get(getattr(source, "profile", "") or "défaut", {}))
        if source.source_type != config.SOURCE_TYPE_DISK_IMAGE:
            opts = {k: v for k, v in opts.items() if k not in profile_catalog.IMAGE_ONLY_KEYS}
        sj = json_builder.build_single_source_json(
            source, tz, taskfile_for(source), scripts_dir, base + ".json", options=opts)
        produced.append(sj)
        # Nom de log = <cas>_<run>_<NN>_<source>.log dans le sous-dossier du run.
        log_path = os.path.join(run_logs_dir, f"{safe}_{run_id}_{prefix}{idx:02d}_"
                                f"{config.sanitize_filename(source.name)}.log")
        cmd = json_builder.import_one_command(exe, user, loc, sub_name, sj, log_path, extra)
        return source.name, cmd

    entries = [emit_source(case, case_name, "", j, s)
               for j, s in enumerate(sources, start=1)]
    bat = json_builder.write_resilient_bat(
        entries, scripts_dir, f"{safe}_import.bat",
        title=f"import resilient - {case_name}")
    produced.append(bat)

    over_limit = limit > 0 and effective > limit
    log(f"Génération mono-cas : {len(sources)} source(s), nouvelles "
        f"{config.human_size(total)}"
        + (f" + existant {config.human_size(existing)}" if existing else "")
        + (f" — ⚠ dépasse la limite {config.human_size(limit)}" if over_limit else "")
        + ".")
    report = {"mode": "single", "total": total, "files": produced,
              "over_limit": over_limit, "overflow": max(0, int(effective - limit)) if over_limit else 0}

    report["existing"] = existing
    report["effective"] = effective
    report["output"] = scripts_dir
    report["logs_dir"] = logs_dir
    report["run_id"] = run_id
    report["run_logs_dir"] = run_logs_dir
    report["oversized"] = sizing.oversized_sources(sources, limit) if limit > 0 else []
    return report
