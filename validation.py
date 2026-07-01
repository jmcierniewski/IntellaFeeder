"""Contrôles amont avant génération.

Important : Intella ne permet pas de revérifier les réglages d'une source
après import. On valide donc le maximum en amont (erreurs bloquantes) et on
signale les points douteux (avertissements non bloquants).
"""

import os

import config
import i18n
import path_parser


def collect(sources, params: dict, tasks_loaded: bool):
    """Retourne ``(errors, warnings)`` : deux listes de chaînes.

    ``errors`` est bloquant ; ``warnings`` est confirmable par l'utilisateur.
    ``tasks_loaded`` indique si le fichier de tâches a pu être lu.
    """
    errors: list[str] = []
    warnings: list[str] = []

    # --- Champs obligatoires ---
    if not params["user"].strip():
        errors.append(i18n.t("validation.user_required", "Le champ « Utilisateur » est obligatoire."))
    if not params["case"].strip():
        errors.append(i18n.t("validation.case_location_required", "L'emplacement du cas est obligatoire."))
    if not params["output"].strip():
        errors.append(i18n.t("validation.output_dir_required", "Le dossier de sortie est obligatoire."))

    exe = params["exe"].strip()
    if not exe:
        errors.append(i18n.t("validation.exe_required", "Le chemin de IntellaCmd.exe est obligatoire."))
    elif not os.path.isfile(exe):
        warnings.append(i18n.t("validation.exe_not_found", "IntellaCmd.exe introuvable : {p}", p=exe))

    if not sources:
        errors.append(i18n.t(
            "validation.no_sources",
            "Aucune source. Collez des chemins puis cliquez sur « Récapituler »."))

    # --- Tâches cochées mais fichier de tâches illisible ---
    if any(s.selected_task_ids for s in sources) and not tasks_loaded:
        errors.append(i18n.t(
            "validation.tasks_unreadable",
            "Des tâches sont cochées mais le fichier de tâches n'a pas pu être lu."))

    # --- Avertissements par source ---
    for s in sources:
        if not os.path.isabs(s.path):
            warnings.append(i18n.t(
                "validation.path_not_absolute",
                "Chemin non absolu (IntellaCmd exige des chemins absolus) : {p}", p=s.path))
        elif not os.path.exists(s.path):
            warnings.append(i18n.t("validation.path_not_found", "Chemin introuvable : {p}", p=s.path))
        if s.source_type == config.SOURCE_TYPE_DISK_IMAGE and path_parser.is_non_first_segment(s.path):
            warnings.append(i18n.t(
                "validation.non_first_segment",
                "Segment d'image peut-être non initial (pointez le 1er, .E01) : {p}", p=s.path))

    return errors, warnings
