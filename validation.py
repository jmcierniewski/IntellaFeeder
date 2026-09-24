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

    # --- Caractères impossibles à citer dans le .bat ---
    # Le nom du cas et l'utilisateur viennent du `case.xml`, pas d'une saisie :
    # un guillemet ou un retour à la ligne y refermerait la citation de la
    # commande IntellaCmd et ferait exécuter ce qui suit (audit du 18/09/2026).
    # `json_builder._q` refuse ces caractères ; ici on le dit AVANT de générer,
    # avec le nom du champ fautif.
    for cle, libelle in (
        ("user", i18n.t("topbar.user", "Utilisateur (du cas)")),
        ("casename", i18n.t("validation.field_case_name", "Nom du cas")),
        ("case", i18n.t("validation.field_case_location", "Emplacement du cas")),
    ):
        valeur = str(params.get(cle, "") or "")
        if any(ch in valeur for ch in '"\r\n'):
            errors.append(i18n.t(
                "validation.unquotable_char",
                "Le champ « {f} » contient un guillemet ou un retour à la ligne, "
                "impossible à transmettre à IntellaCmd. Corrigez-le (pour un nom "
                "ou un utilisateur issu du case.xml, corrigez-le dans Intella).",
                f=libelle))

    if not sources:
        errors.append(i18n.t(
            "validation.no_sources",
            "Aucune source. Collez des chemins puis cliquez sur « Analyser les chemins »."))

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
