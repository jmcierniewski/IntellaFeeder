r"""Traductions embarquees dans l'executable (module .py, pas un fichier de donnees).

Ce module contient les langues **integrees** (FR, US) : PyInstaller les embarque
comme n'importe quel module source -- pas de ``--add-data``, pas de dossier
externe requis pour que l'appli fonctionne des sa premiere installation. Elle
tourne donc en FR/US meme si le dossier ``lang\`` n'existe pas du tout a cote
de l'exe.

Un fichier externe ``lang\<CODE>.lang`` (JSON, meme structure : ``strings`` +
``help``) reste possible et est **toujours prioritaire** sur son equivalent
integre ici -- pratique pour corriger une traduction ou ajouter une langue sans
reconstruire l'exe (voir ``i18n._read``). ``lang/FR.lang`` et ``lang/US.lang``
peuvent etre conserves a cote du script pour l'edition ; ils sont facultatifs
une fois l'exe construit.

Genere a partir de ``lang/FR.lang`` et ``lang/US.lang`` -- si ces .lang evoluent
et que l'evolution doit etre embarquee, regenerer ce module (voir CLAUDE.md).
"""

BUILTIN = {
    "FR": {
        "strings": {
            "app.title": "IntellaFeeder — Générateur de sources d'import Intella",
            "topbar.title": "Paramètres communs",
            "topbar.user": "Utilisateur (du cas)",
            "topbar.exe": "IntellaCmd.exe *",
            "topbar.exe_locked": "(verrouillé via .ini)",
            "topbar.exe_dialog": "IntellaCmd.exe",
            "topbar.language": "Langue",
            "topbar.language_restart": "La langue choisie sera appliquée au prochain démarrage de l'application.",
            "common.browse": "Parcourir…",
            "common.yes": "oui",
            "common.no": "non",
            "unit.gb": "Go",
            "unit.mb": "Mo",
            "common.filetype_text": "Texte",
            "common.filetype_all": "Tous",
            "journal.export": "Exporter le journal…",
            "journal.clear": "Effacer",
            "journal.cleared": "Journal effacé.",
            "journal.filetype_log": "Journal",
            "journal.exported_log": "Journal exporté : {p}",
            "journal.exported_msg": "Journal exporté :\n{p}",
            "journal.export_failed": "Échec de l'export :\n{e}",
            "common.extra_args": "Arguments suppl.",
            "common.export_csv": "Exporter en CSV…",
            "common.case_required_title": "Cas requis",
            "common.fields_required_title": "Champs requis",
            "common.exported_to": "Exporté :\n{p}",
            "common.export_failed": "Échec :\n{e}",
            "common.export_title": "Export",
            "col.name": "Nom",
            "col.type": "Type",
            "col.timezone": "Fuseau",
            "col.size": "Taille",
            "col.bytes": "Octets",
            "col.segments": "Segments",
            "col.path": "Chemin",
            "col.tasks": "Tâches",
            "inventory.case_frame": "Cas à inventorier",
            "inventory.case_folder": "Dossier du cas",
            "inventory.autolicense": "Sélection auto de licence (-autoSelectFullProcessingLicense)",
            "inventory.run": "Lire les sources (IntellaCmd)",
            "inventory.scan": "Scanner les dossiers à 0",
            "inventory.export_xml": "Exporter le XML…",
            "inventory.export_tasks": "Exporter les tâches du cas…",
            "inventory.info_profile": "Info Profil →",
            "inventory.no_case": "Aucun cas sélectionné.",
            "inventory.pick_case_title": "Dossier du cas Intella",
            "inventory.not_a_case": "⚠ Pas un dossier de cas Intella (case.xml absent).",
            "inventory.case_folder_title": "Dossier de cas",
            "inventory.xml_unreadable": "⚠ case.xml illisible.",
            "inventory.xml_read_failed": "Lecture de case.xml impossible :\n{e}",
            "inventory.case_detected_log": "Cas détecté : « {n} » — créé par {u}, {s} occupé(s).",
            "inventory.case_detected_summary": "Cas « {n} » — {s} occupé(s). « Lire les sources » pour le dédoublonnage.",
            "inventory.case_required_body": "Sélectionnez d'abord un dossier de cas valide (case.xml détecté).",
            "inventory.exe_required": "Renseignez IntellaCmd.exe (en haut).",
            "inventory.user_required": "Utilisateur introuvable dans case.xml.",
            "inventory.reading": "Lecture en cours…",
            "inventory.reading_log": "Inventaire des sources du cas : {c}",
            "inventory.read_failed": "Échec de la lecture (voir Journal).",
            "inventory.read_error_log": "Erreur inventaire : {m}",
            "inventory.sources_title": "Inventaire des sources",
            "inventory.n_sources_read": "{n} source(s) lue(s) dans le cas.",
            "inventory.n_cached_folders": "{n} dossier(s) déjà mesuré(s) repris du fichier {f}.",
            "inventory.n_unknown_folders": "{n} dossier(s) sans taille reportée — bouton « Scanner les dossiers à 0 » pour les mesurer.",
            "inventory.cache_applied_log": "{n} dossier(s) à 0 repris du cache {f} (total {t}).",
            "inventory.size_mismatch_log": "Cohérence tailles : case.xml {c} < somme sources {s} (écart {p:.1f}%). Garde-fou dépassement basé sur {b}.",
            "inventory.size_mismatch_title": "Cohérence des tailles",
            "inventory.size_mismatch_body": "La taille occupée du cas (case.xml : {c}) est inférieure de {p:.1f}% à la somme des sources lues ({s}).\n\nCertaines sources listées ne semblent pas (entièrement) indexées dans le cas.\n\nLe calcul d'un éventuel dépassement utilisera la valeur la plus grande ({b}).",
            "inventory.case_empty": "Cas « {n} » — vide (aucune source indexée).",
            "inventory.case_summary": "Cas « {n} » — {c} source(s) — taille du cas {s}",
            "inventory.n_scannable_folders": "{n} dossier(s) à 0 (scannables)",
            "inventory.zero_folders_title": "Dossiers à 0",
            "inventory.zero_folders_none": "Aucun dossier sans taille à mesurer.\nLisez d'abord les sources du cas.",
            "inventory.scan_start_log": "Scan de {n} dossier(s) à taille 0…",
            "inventory.measuring_progress": "Mesure des dossiers… {i}/{n}",
            "inventory.measuring_progress_named": "Mesure des dossiers… {i}/{n} : {f}",
            "inventory.sizes_saved_log": "Tailles mémorisées dans {f}.",
            "inventory.folders_measured_log": "Dossiers mesurés : {n} — total {t}.",
            "inventory.folders_measured_summary": "{n} dossier(s) mesuré(s) — total {t} (intégré à la somme inventaire).",
            "inventory.default_profile_name": "profil",
            "inventory.info_profile_no_inventory": "Lisez d'abord les sources du cas (« Lire les sources »).",
            "inventory.info_profile_no_selection": "Sélectionnez une source dans le tableau.",
            "inventory.info_profile_not_found": "Source introuvable (re-lisez les sources).",
            "inventory.info_profile_empty": "La source « {n} » n'expose aucun réglage exploitable (indexOptions/domainBoundaries vides).",
            "inventory.info_profile_log": "Info Profil : réglages de « {n} » transférés à l'onglet Profils ({c} option(s)).",
            "inventory.export_xml_none": "Aucun XML disponible.\nLancez d'abord « Lire les sources ».",
            "inventory.export_xml_log": "XML des sources exporté : {p}",
            "inventory.export_tasks_none": "Aucune tâche sur les sources de ce cas.\nLisez d'abord les sources (« Lire les sources »).",
            "inventory.export_tasks_log": "Tâches du cas exportées ({n} tâche(s) dédupliquée(s)) : {p}",
            "inventory.export_tasks_msg": "{n} tâche(s) dédupliquée(s) exportée(s) :\n{p}\n\n1 objet = 1 tâche logique (UUID par source fusionnés par signature).",
            "inventory.export_csv_none": "Lisez d'abord les sources d'un cas.",
            "inventory.export_csv_log": "Inventaire exporté en CSV : {p}",
            "common.save": "Enregistrer",
            "common.delete": "Supprimer",
            "group.mail": "Messagerie & e-mails",
            "group.chats": "Chats & conversations",
            "group.archives": "Archives & bases de données",
            "group.windows": "Système Windows",
            "group.browser": "Web & navigateurs",
            "group.images": "Images disque & récupération",
            "group.vsc": "Volume Shadow Copies (images)",
            "group.text": "Texte & analyse",
            "group.filters": "Filtres",
            "group.cache": "Cache & avancé",
            "opt.indexMailArchives": "Indexer les archives de messagerie",
            "opt.emailsGeolocationEnabled": "Géolocalisation des e-mails",
            "opt.indexChatMessages": "Indexer les messages de chat",
            "opt.processingMode": "Mode de traitement des chats",
            "opt.splitMode": "Découpage des conversations",
            "opt.numberMessagesPerConversation": "Messages max / conversation",
            "opt.indexArchives": "Indexer les archives (zip, rar…)",
            "opt.indexDatabases": "Indexer les bases de données",
            "opt.indexWindowsRegistry": "Indexer le registre Windows",
            "opt.indexWindowsEventLog": "Indexer les journaux d'événements Windows",
            "opt.indexBrowserHistory": "Indexer l'historique de navigation",
            "opt.recoverDeleted": "Récupérer les fichiers supprimés",
            "opt.carveUnallocatedSpace": "Carving de l'espace non alloué",
            "opt.verifyAff4Hashes": "Vérifier les hachages AFF4",
            "opt.indexVolumeShadowCopies": "Indexer les clichés VSS",
            "opt.suppressUnchangedFilesInVsc": "Supprimer les fichiers inchangés (VSS)",
            "opt.preferNewestFilesInVsc": "Préférer les fichiers les plus récents (VSS)",
            "opt.indexChangedLastAccessFilesInVsc": "Tenir compte du dernier accès (VSS)",
            "opt.indexEmbeddedImages": "Indexer les images embarquées",
            "opt.analyseParagraphs": "Analyser les paragraphes",
            "opt.indexUnstructured": "Indexer le contenu non structuré",
            "opt.sourceTypeFilter": "Filtre de types MIME (séparés par des virgules)",
            "opt.sourceTypeFilterMode": "Mode du filtre de types",
            "opt.sourceHashFilters": "Listes de hachages (.md5, séparées par des virgules)",
            "opt.fileNameFilters": "Filtre de noms de fichiers",
            "opt.cacheEvidenceFiles": "Mettre les preuves en cache",
            "opt.maxBinarySizeToStore": "Taille binaire max stockée",
            "opt.custodian": "Dépositaire (custodian)",
            "opt.enableCrawlerScript": "Activer un script de crawler",
            "opt.sourceCrawlerScriptType": "Type de script de crawler",
            "opt.sourceCrawlerScriptFile": "Fichier de script de crawler",
            "profiles.intro": "Un profil = jeu de paramètres d'analyse appliqué à une source à l'import (affecté dans l'onglet « 2. Import », colonne « Profil »). Le profil « défaut » applique les réglages par défaut d'Intella (aucune option forcée). Seules les valeurs différentes du défaut sont enregistrées et émises.",
            "profiles.saved": "Profils enregistrés",
            "profiles.name_label": "Nom du profil",
            "profiles.new": "Nouveau",
            "profiles.rename": "Renommer…",
            "profiles.comments": "Commentaires",
            "profiles.analysis_options": "Options d'analyse",
            "profiles.to_verify": "à éprouver",
            "profiles.images_only": "[images]",
            "profiles.filename_filter_tip": "Jokers autorisés dans les noms de fichiers : « ? » (un caractère) et « * » (plusieurs). Ex. : rapport_*.pdf, IMG_????.jpg",
            "profiles.name_required": "Indiquez un nom de profil.",
            "profiles.default_reserved": "Le profil « défaut » est réservé.",
            "profiles.overwrite_confirm": "Le profil « {n} » existe déjà. Le mettre à jour ?",
            "profiles.saved_log": "Profil enregistré : « {n} ».",
            "profiles.saved_msg": "Profil « {n} » enregistré.",
            "profiles.select_non_default": "Sélectionnez un profil (≠ « défaut »).",
            "profiles.rename_title": "Renommer le profil",
            "profiles.new_name": "Nouveau nom :",
            "profiles.renamed_log": "Profil renommé : « {o} » → « {n} ».",
            "profiles.delete_confirm": "Supprimer le profil « {n} » ?",
            "profiles.deleted_log": "Profil supprimé : « {n} ».",
            "profiles.err_name_empty": "Le nom du profil est vide.",
            "profiles.err_default_reserved": "Le profil « défaut » est réservé et non modifiable.",
            "profiles.err_default_no_delete": "Le profil « défaut » ne peut pas être supprimé.",
            "profiles.err_default_reserved_short": "Le profil « défaut » est réservé.",
            "profiles.err_new_name_empty": "Le nouveau nom est vide.",
            "profiles.err_not_found": "Profil introuvable : {n}",
            "profiles.err_already_exists": "Un profil « {n} » existe déjà.",
            "tabs.inventory": "1. Inventaire du cas",
            "tabs.detail": "Détail du cas",
            "tabs.import": "2. Import",
            "tabs.profiles": "Profils",
            "tabs.journal": "Journal",
            "tabs.help": "Aide",
            "detail.no_case": "Sélectionnez un cas dans l'onglet « 1. Inventaire du cas ».",
            "detail.h1_case": "Cas",
            "detail.name": "Nom",
            "detail.folder": "Dossier",
            "detail.description": "Description",
            "detail.id": "Identifiant",
            "detail.created": "Créé le",
            "detail.last_opened": "Dernière ouverture",
            "detail.created_by": "Créé par",
            "detail.size": "Taille occupée",
            "detail.size_value": "{h}  ({b:,} octets)",
            "detail.version": "Version (origine / actuelle)",
            "detail.h1_prefs": "Préférences du cas",
            "detail.optim_folder": "Dossier d'optimisation",
            "detail.authorized_users": "Utilisateurs autorisés",
            "detail.email_threading": "Email Threading effectué",
            "detail.saved_searches": "Recherches enregistrées effectuées",
            "detail.hash_algo": "Hachage des messages",
            "detail.h1_tasks2": "Tâches post-indexation (tasks2.json)",
            "detail.no_tasks2": "Aucune tâche post-indexation déclarée.",
            "import.already_used": "déjà {s} occupé(s)",
            "import.and_n_more": "… et {n} autre(s).",
            "import.auto_removed_log": "{n} source(s) déjà indexée(s) retirée(s) automatiquement.",
            "import.case_label": "Cas :",
            "import.case_prefix": "Cas « {n} » : ",
            "import.case_tasks": "Tâches du cas (inventaire)",
            "import.case_tasks_none": "Aucune tâche n'est définie sur les sources de ce cas.",
            "import.case_tasks_not_loaded": "La liste des sources du cas n'est pas chargée.\nLancez « Lire les sources » dans l'onglet « 1. Inventaire du cas ».",
            "import.case_tasks_recycled_log": "Tâches recyclées depuis l'inventaire du cas : {n} tâche(s).",
            "import.case_tasks_recycled_msg": "{n} tâche(s) du cas chargée(s) (dédupliquées).\nElles s'appliquent comme un fichier de tâches : cochez-les par source.",
            "import.case_tasks_unreadable": "Tâches illisibles :\n{e}",
            "import.check_all": "Imp. : tout cocher",
            "import.close": "Fermer",
            "import.col_delete": "Suppr.",
            "import.col_import": "Imp.",
            "import.col_import_log": "Log d'import",
            "import.col_in_case": "Dans le cas",
            "import.col_name": "Nom de la source",
            "import.col_profile": "Profil",
            "import.col_source": "Source",
            "import.compute_size": "Calculer la taille",
            "import.computing_missing_sizes_log": "Calcul des tailles manquantes (sources cochées) avant génération…",
            "import.computing_size_log": "Calcul de la taille de {n} source(s) cochée(s)…",
            "import.corrections_needed": "Corrections nécessaires",
            "import.default_profile_label": "Profil par défaut :",
            "import.empty": "vide",
            "import.empty_selection_body": "Cochez au moins une source dans la colonne « Imp. » (Importer).",
            "import.empty_selection_title": "Sélection vide",
            "import.export_list": "Exporter la liste…",
            "import.folders_panel": "Dossiers standard (FOLDER_OR_FILE) — 1 chemin/ligne",
            "import.generate": "Générer les fichiers d'import",
            "import.generate_anyway": "Générer malgré tout ?",
            "import.images_panel": "Images forensiques (DISK_IMAGE) — 1 chemin/ligne",
            "import.import_list": "Importer une liste…",
            "import.integrity_check_log": "Vérification d'intégrité des sources : ",
            "import.integrity_disabled_log": "DÉSACTIVÉE (« {a} » ajouté aux arguments).",
            "import.integrity_enabled_log": "activée (argument retiré).",
            "import.integrity_title": "Intégrité des sources",
            "import.inventory_exceeds": "(somme inventaire > case.xml {s})",
            "import.launch_failed_log": "Échec du lancement de l'import : {e}",
            "import.launch_impossible": "Lancement impossible :\n{e}",
            "import.launched_log": "Import lancé : {b}",
            "import.limit_exceeded_body": "La limite de {lim:g} Go serait dépassée.\n\n{n} source(s) ({v}) ont été DÉCOCHÉES (la partie qui tient reste cochée) :\n{list}\n\nRien n'a été généré. Vérifiez / ajustez les coches « Imp. », puis relancez « Générer » pour importer ce que vous gardez.\n\nPour le reste : créez le sous-cas manuellement dans Intella, ciblez-le comme cas, recochez et réimportez.",
            "import.limit_exceeded_log": "Dépassement limite : {n} source(s) décochée(s) ({v}). Génération suspendue — ajustez les coches puis relancez « Générer ».",
            "import.limit_exceeded_title": "Limite atteinte — génération suspendue",
            "import.limit_label": "Limite / cas (Go)",
            "import.limit_status": "{etat} la limite ({eff} / {lim})",
            "import.list_imported_log": "Récapitulatif importé : {n} source(s) depuis {p}",
            "import.list_imported_removed": "({n} déjà dans le cas, retirée(s)).",
            "import.list_invalid_format": "Format invalide (liste de sources attendue).",
            "import.list_replace_confirm": "Remplacer le récapitulatif actuel ({cur} source(s)) par {new} source(s) du fichier ?",
            "import.list_unreadable": "Lecture impossible :\n{e}",
            "import.location_label": "Emplacement :",
            "import.log_failed": "ÉCHEC : {m}",
            "import.log_ok": "OK",
            "import.n_indexed": "{n} source(s) indexée(s)",
            "import.n_removed_auto": "{n} déjà indexée(s) dans le cas, retirée(s) automatiquement.",
            "import.n_sources_loaded": "{n} source(s) chargée(s).",
            "import.no_bat_found": "Aucun fichier d'import trouvé pour ce cas.\nCliquez d'abord sur « Générer les fichiers d'import ».",
            "import.no_case_selected": "ⓘ Aucun cas sélectionné — choisissez-le dans l'onglet « 1. Inventaire du cas ».",
            "import.no_checked": "Aucune source cochée « Importer ».\nSeules les lignes cochées sont mesurées.",
            "import.no_inventory_read": "⚠ liste des sources non lue (onglet 1) → pas de dédoublonnage.",
            "import.no_rows_to_export": "Aucune ligne à exporter.",
            "import.over_limit": "⚠ dépasse",
            "import.partial": "(partiel)",
            "import.profile_applied_all_log": "Profil « {p} » appliqué à toutes les sources ({n}).",
            "import.recap_empty": "Le récapitulatif est vide.",
            "import.recap_exported_log": "Récapitulatif exporté ({n} source(s)) : {p}",
            "import.recap_exported_msg": "{n} source(s) exportée(s) :\n{p}",
            "import.recap_frame": "Récapitulatif des sources",
            "import.reload_tasks": "Recharger les tâches",
            "import.report_done": "Génération terminée — {n} source(s) importée(s).",
            "import.report_existing": "Déjà dans le cas : {e}  →  total {t}.",
            "import.report_folder": "Dossier : {d}",
            "import.report_new_volume": "Volume des nouvelles sources : {v}.",
            "import.report_no_subcase": "Aucun sous-cas n'est créé automatiquement : créez-le manuellement dans Intella puis réimportez le reste.",
            "import.report_open_folder": "Ouvrir le dossier des scripts ?",
            "import.report_over_limit": "⚠ Le total dépasse la limite de {lim:g} Go de {ov}.",
            "import.report_oversized": "⚠ Source(s) seule(s) > limite (non fractionnable) : {n}",
            "import.report_resilient": "Import résilient : 1 commande par source, log par source.",
            "import.report_run_logs": "Logs de ce run : logs\\{r}\\ (« Valider les opérations » lira ce run).",
            "import.report_single_case": "Un seul cas (sous la limite).",
            "import.report_title": "Terminé",
            "import.run_confirm": "Lancer l'import dans Intella ?\n\n{b}\n\nIntellaCmd va ajouter les sources au cas (action non réversible côté cas). Une fenêtre de console s'ouvre et affiche la progression.\n\nContinuer ?",
            "import.run_import": "Importer (lancer le .bat)",
            "import.select_case_first": "Sélectionnez d'abord un cas (onglet « 1. Inventaire du cas »).",
            "import.select_case_short": "Sélectionnez d'abord un cas (onglet « 1. Inventaire du cas »).",
            "import.select_case_target": "Sélectionnez d'abord un cas dans l'onglet « 1. Inventaire du cas ».",
            "import.size_done_log": "Calcul des tailles terminé. Total cochées : {t}.",
            "import.size_title": "Taille",
            "import.skip_integrity": "Ne pas vérifier l'intégrité des sources (images multi-tronçons — contourne le bug Vound)",
            "import.source_removed_log": "Source retirée du récapitulatif : {n}",
            "import.summarize": "▼ Récapituler",
            "import.summary_log": "Récapitulatif : {n} source(s).",
            "import.summary_removed_log": "{n} déjà dans le cas, retirée(s).",
            "import.target_case_frame": "Cas cible (défini par l'onglet « 1. Inventaire du cas »)",
            "import.tasks_check_all": "Tâches : tout cocher",
            "import.tasks_file_label": "Fichier de tâches",
            "import.tasks_file_loaded_log": "Fichier de tâches chargé : {n} tâche(s).",
            "import.tasks_file_not_found": "Introuvable :\n{p}",
            "import.tasks_file_read_error_log": "Erreur lecture fichier de tâches : {e}",
            "import.tasks_file_title": "Fichier de tâches",
            "import.tasks_file_unavailable_log": "Fichier de tâches indisponible (champ vidé ou fichier absent) : utilisation des définitions déjà chargées en mémoire.",
            "import.tasks_file_unreadable": "Lecture impossible :\n{e}",
            "import.tasks_uncheck_all": "Tâches : tout décocher",
            "import.timezone_label": "Fuseau horaire",
            "import.total_summary": "{n} source(s), {c} à importer — taille cochées : {t}{suffix}",
            "import.uncheck_all": "Imp. : tout décocher",
            "import.under_limit": "sous",
            "import.validate": "Valider les opérations",
            "import.validate_absent": "  ✗ {n} : absente du cas (aucun log d'import correspondant).",
            "import.validate_failed": "  ✗ {n} : échec — {m}",
            "import.validate_head": "Cas « {c} » : {n} source(s) présente(s).  Sur {v} vérifiée(s) : {ok} dans le cas, {ko} absente(s).  {l} log(s) analysé(s).",
            "import.validate_other": "  • {n} : {m}",
            "import.validate_present": "  ✔ {n} : présente dans le cas.",
            "import.validate_requires": "IntellaCmd.exe et l'utilisateur sont requis.",
            "import.validate_rescan_failed_log": "Validation : échec du re-scan : {m}",
            "import.validate_run_analyzed": "  Run analysé : {r}.",
            "import.validate_run_suffix": " (run {r})",
            "import.validate_start_log": "Validation des opérations : re-scan du cas + analyse des logs…",
            "import.validate_summary_log": "Validation{r} : {n} source(s) dans le cas, {l} log(s) analysé(s).",
            "import.validation_exported_log": "Validation exportée en CSV : {p}",
            "import.warnings_title": "Avertissements",
            "import.write_title": "Écriture",
            "import.zero_sources": "0 source",
            "type.folder": "Dossier",
            "type.image": "Image",
            "validation.case_location_required": "L'emplacement du cas est obligatoire.",
            "validation.exe_not_found": "IntellaCmd.exe introuvable : {p}",
            "validation.exe_required": "Le chemin de IntellaCmd.exe est obligatoire.",
            "validation.no_sources": "Aucune source. Collez des chemins puis cliquez sur « Récapituler ».",
            "validation.non_first_segment": "Segment d'image peut-être non initial (pointez le 1er, .E01) : {p}",
            "validation.output_dir_required": "Le dossier de sortie est obligatoire.",
            "validation.path_not_absolute": "Chemin non absolu (IntellaCmd exige des chemins absolus) : {p}",
            "validation.path_not_found": "Chemin introuvable : {p}",
            "validation.tasks_unreadable": "Des tâches sont cochées mais le fichier de tâches n'a pas pu être lu.",
            "validation.user_required": "Le champ « Utilisateur » est obligatoire.",
            "import.size_cache_reused_log": "{n} source(s) déjà mesurée(s) reprise(s) du cache (IF_<cas>.info).",
            "task_builder.err_not_array": "Les tâches doivent être un tableau JSON (format exporté par Intella).",
            "task_builder.default_task_name": "Tâche {n}",
            "case_meta.err_no_case_xml": "case.xml introuvable à cet emplacement. Vérifiez que vous pointez bien sur le dossier d'un cas Intella.",
            "op_validation.log_unreadable": "Log illisible : {e}",
            "op_validation.added_but": "Ajout OK mais : {m}",
            "op_validation.no_confirmation": "Aucune confirmation d'ajout dans le log."
        },
        "help": [
            [
                "h1",
                "IntellaFeeder — Aide"
            ],
            [
                "p",
                "Cet outil prépare l'import automatique de sources dans un cas Intella déjà créé, sans repasser par l'assistant web. Vous collez des listes de chemins, choisissez les tâches à appliquer, et l'outil génère les fichiers et un script « .bat » prêt à lancer."
            ],
            [
                "h1",
                "Déroulé recommandé"
            ],
            [
                "b",
                "1. Onglet « Inventaire du cas » : lisez d'abord les sources déjà présentes dans le cas. Cela sert à connaître le volume déjà occupé et à repérer les sources déjà indexées (pour ne pas les ajouter deux fois). Le bouton « Exporter le XML » enregistre une copie de la liste lue."
            ],
            [
                "b",
                "2. Onglet « Import » : collez les chemins des nouvelles sources (1 chemin par ligne) — images forensiques à gauche, dossiers/fichiers à droite."
            ],
            [
                "b",
                "3. Cliquez « Récapituler » : le tableau liste les sources. Les sources déjà présentes dans le cas (d'après l'inventaire) sont surlignées."
            ],
            [
                "b",
                "4. Cliquez « Calculer la taille » pour connaître le volume des sources. Cette étape est FACULTATIVE : l'outil utilise déjà, par défaut, la taille occupée déclarée dans le fichier case.xml du cas (récupérée à l'onglet « 1. Inventaire du cas »). Mais ce chiffre ne compte pas les sources déjà référencées dans Intella tant qu'elles n'ont pas été indexées (une source ajoutée à un cas peut rester en attente d'indexation) — il peut donc sous-estimer le volume réellement occupé. « Calculer la taille » mesure directement sur le disque les nouvelles sources cochées, pour un garde-fou plus fiable si vous approchez de la limite. Le résultat de chaque mesure est enregistré dans un fichier créé à la racine du dossier du cas (IF_<nom du cas>.info) : une source déjà mesurée lors d'une session précédente n'est pas rescannée."
            ],
            [
                "b",
                "5. Cochez, pour chaque source, les tâches annexes à exécuter (colonnes T1, T2…)."
            ],
            [
                "b",
                "6. Cliquez « Générer » : l'outil écrit les fichiers de sortie et le(s) script(s) « .bat ». Lancez le « .bat » pour réaliser l'import dans Intella."
            ],
            [
                "h1",
                "Astuces de l'interface"
            ],
            [
                "b",
                "Nom réel d'une tâche : passez la souris sur l'en-tête d'une colonne T1, T2… (ou sur ses boutons ✓ / ✗) pour afficher le nom complet de la tâche."
            ],
            [
                "b",
                "Tri : cliquez sur un en-tête de colonne pour trier (une flèche ▲ / ▼ indique le sens). Un nouveau clic inverse le tri."
            ],
            [
                "b",
                "Défilement horizontal : la barre du bas permet de voir toutes les colonnes de tâches quand elles sont nombreuses."
            ],
            [
                "b",
                "Renommer une source : double-cliquez sur son nom dans le tableau. Cela ne change QUE le libellé affiché dans Intella (nom de la source) — le chemin réellement intégré (le fichier/dossier pointé) n'est pas modifié : la source d'origine est intégrée normalement. Utile pour donner un nom plus lisible qu'un nom de fichier technique, sans rien changer à ce qui est indexé."
            ],
            [
                "b",
                "Cocher / décocher vite : « Tout cocher / décocher », ou les boutons « T1 ✓ / T1 ✗ » pour (dé)cocher toute une colonne d'un coup."
            ],
            [
                "b",
                "Guillemets : vous pouvez coller des chemins entre guillemets, ils sont nettoyés automatiquement."
            ],
            [
                "b",
                "Images en plusieurs morceaux (.E01/.E02… ou .ad1/.ad2…) : indiquez seulement le PREMIER segment ; les autres sont pris en compte tout seuls."
            ],
            [
                "h1",
                "Profils de paramètres d'analyse"
            ],
            [
                "p",
                "Un « profil » regroupe des réglages d'indexation (messagerie, archives, récupération de fichiers supprimés, filtres…) que vous appliquez à une source à l'import. Ils se créent dans l'onglet « Profils » et sont partagés entre vos cas."
            ],
            [
                "b",
                "Dans l'onglet « Profils » : choisissez un profil dans la liste pour voir ses options, ou « Nouveau » pour partir des réglages par défaut. Cochez les options voulues, donnez un nom, puis « Enregistrer »."
            ],
            [
                "b",
                "Le profil « défaut » applique les réglages standard d'Intella : il ne force aucune option et n'est pas modifiable."
            ],
            [
                "b",
                "Astuce « Info Profil » : réglez une source d'exemple dans Intella, puis dans l'onglet « Inventaire du cas », lisez les sources, sélectionnez cette source et cliquez « Info Profil → ». Ses réglages (y compris le filtre de types) remplissent automatiquement l'onglet Profils : il ne reste qu'à nommer et enregistrer le profil."
            ],
            [
                "b",
                "Chaque profil est enregistré dans un fichier du dossier « profils » (à côté du programme) ; vous pouvez les sauvegarder ou les partager. Le champ « Commentaires » (en haut) permet d'y noter à quoi sert le profil."
            ],
            [
                "b",
                "Filtre de nom de fichiers : vous pouvez utiliser les jokers « ? » (un caractère) et « * » (plusieurs caractères), ex. rapport_*.pdf."
            ],
            [
                "b",
                "Filtre de types MIME : c'est une longue liste ; la zone s'agrandit quand vous cliquez dedans pour copier/coller plus facilement."
            ],
            [
                "b",
                "Dans le récapitulatif de l'onglet Import, la colonne « Profil » permet de choisir le profil de chaque source. Le menu « Profil par défaut » applique le profil choisi à toutes les lignes d'un coup."
            ],
            [
                "h1",
                "Types MIME pour le filtre de types"
            ],
            [
                "p",
                "Le champ « Filtre de types MIME » attend une liste séparée par des virgules, à combiner avec le mode « inclure » ou « exclure ». Cette liste mélange DEUX niveaux qui cohabitent :"
            ],
            [
                "b",
                "Les CATÉGORIES Intella (« category/… ») : de vrais regroupements thématiques d'Intella. Cocher une catégorie sélectionne d'un coup tous les formats qu'elle contient."
            ],
            [
                "b",
                "Les TYPES INDIVIDUELS (« application/x-pdf », « application/rtf »…) : un format précis, coché à l'unité, indépendamment de sa catégorie."
            ],
            [
                "p",
                "Un type individuel n'est donc PAS « contenu » dans un « category/… » de la liste : les deux se choisissent séparément. Exemple : application/x-pdf relève thématiquement des Documents, mais se coche seul (Intella n'imbrique pas). La liste exacte dépend de votre cas — le plus fiable est d'utiliser « Info Profil » sur une source réglée dans Intella."
            ],
            [
                "h2",
                "Catégories Intella (les vraies catégories)"
            ],
            [
                "pcsv",
                "category/accounts, category/browser_cookies, category/browser_downloads, category/chat, category/contacts, category/containers, category/crypto_currency, category/formulas, category/graphics, category/hangul_document, category/launched_programs, category/media, category/other_communications, category/other_documents, category/other_media, category/others, category/presentations, category/recently_accessed_files, category/scheduling, category/system, category/user_activity, category/user_sessions, category/video, category/voice, category/word_processing"
            ],
            [
                "h2",
                "Types individuels (formats précis)"
            ],
            [
                "p",
                "Ce ne sont PAS des catégories Intella. Le regroupement par thème ci-dessous est le nôtre, uniquement pour faciliter la lecture."
            ],
            [
                "bcsv",
                "Traitement de texte & bureautique : application/rtf, text/rtf, application/x-pdf, application/msonenote, application/vnd.fdf, application/vnd.framemaker, application/x-framemaker, application/vnd.ms-publisher, application/vnd.ms-xpsdocument, application/vnd.oasis.opendocument.text (et -master, -template, -web), application/vnd.stardivision.writer (et -global), application/vnd.stardivision.math, application/vnd.stardivision.draw, application/vnd.sun.xml.writer (et .template), application/vnd.wordperfect, application/wps-office.wps/.wpt/.dpt/.ett, application/x-mspowerpoint, text/vnd.wap.wml"
            ],
            [
                "bcsv",
                "Images, vidéo & média : image/iff, image/x-iff, application/iff, application/x-iff, application/ogg, application/riff, application/x-iso-base-media, application/x-shockwave-flash, video/x-ms-asf, video/x-ms-wm"
            ],
            [
                "bcsv",
                "Archives & conteneurs : application/binhex, application/unix-v7-tar, application/x-java-webarchive, application/x-rar-compressed-v5, application/x-sitx"
            ],
            [
                "bcsv",
                "Artefacts Windows & forensic (Intella) : application/vnd.ms-registry, application/vnd.ms-registry-key, application/vnd.ms-windows-xml-event-log-entry, application/x-intella-windows-registry-artifacts, application/x-intella-windows-shellbag, application/x-intella-windows-10-timeline-entry, application/x-intella-windows-push-notification-entry, application/x-intella-operating-system-information, application/x-intella-startup-program, application/x-intella-installed-application, application/x-intella-time-zone-information, application/x-intella-usb-storage-device, application/x-intella-boot-sector-file, application/x-intella-net-connection, application/x-intella-device-acquisition, application/x-intella-aws-s3-bucket, application/x-intella-imap-connection, application/x-intella-sharepoint-post"
            ],
            [
                "bcsv",
                "Réseau & e-mail : application/pcap, application/vnd.tcpdump.pcap, message/rfc822-headers, application/applefile, multipart/appledouble"
            ],
            [
                "h1",
                "Images en plusieurs morceaux : intégrité"
            ],
            [
                "p",
                "Une anomalie connue de l'éditeur (Vound) peut faire échouer la vérification d'intégrité des images forensiques découpées en plusieurs fichiers. En attendant un correctif, l'onglet Import propose une case « Ne pas vérifier l'intégrité des sources »."
            ],
            [
                "b",
                "Quand elle est cochée, l'option « -validateDiskImage false » est ajoutée automatiquement au champ « Arguments suppl. » : l'import n'effectue plus la vérification d'intégrité. Le réglage est mémorisé pour chaque cas."
            ],
            [
                "h1",
                "Éviter la double indexation"
            ],
            [
                "p",
                "Après avoir lu l'inventaire d'un cas, l'onglet Import compare les chemins que vous collez avec ceux déjà indexés. Les sources déjà présentes sont retirées automatiquement du récapitulatif (au « Récapituler » comme à l'import d'une liste)."
            ],
            [
                "h1",
                "Quand le cas devient trop grand"
            ],
            [
                "p",
                "Un cas Intella est limité (ici 950 Go par sécurité, sur 1 To autorisé). L'outil additionne le volume déjà présent dans le cas et celui des nouvelles sources :"
            ],
            [
                "b",
                "Si le total tient sous la limite : un seul import, dans le cas existant."
            ],
            [
                "b",
                "Si le total dépasse la limite : l'outil PRÉVIENT, décoche automatiquement les dernières sources pour ne garder que ce qui tient, et SUSPEND la génération (rien n'est écrit). Aucun sous-cas n'est créé automatiquement."
            ],
            [
                "b",
                "Marche à suivre : vérifiez/ajustez les cases « Imp. » puis relancez « Générer » pour importer ce que vous gardez. Pour le reste : créez le sous-cas manuellement dans Intella, ciblez-le comme cas, recochez et réimportez les sources restantes."
            ],
            [
                "b",
                "La colonne « Imp. » (case à cocher) choisit les sources à mesurer et à importer ; la croix « ✕ » retire une ligne du récapitulatif. Les boutons « Exporter / Importer une liste » sauvegardent l'état du récapitulatif."
            ],
            [
                "b",
                "Une source seule plus grande que la limite ne peut pas être importée telle quelle : elle est signalée."
            ],
            [
                "p",
                "Remarque : le volume des sources de type « dossier » n'est pas toujours connu via l'inventaire ; dans ce cas le total affiché est marqué « partiel » et la décision peut être optimiste. Vérifiez ces dossiers si vous êtes proche de la limite."
            ],
            [
                "h1",
                "Fichiers de langue"
            ],
            [
                "p",
                "Le dossier « lang » (à côté du programme) contient les fichiers FR.lang et US.lang. Ces fichiers sont FACULTATIFS : le français et l'anglais sont déjà intégrés à l'application (codés en dur), qui fonctionne donc normalement même si ce dossier est absent. Ils peuvent servir d'exemple pour créer une traduction dans une autre langue."
            ]
        ]
    },
    "US": {
        "strings": {
            "app.title": "IntellaFeeder — Intella import source generator",
            "topbar.title": "Common settings",
            "topbar.user": "User (from case)",
            "topbar.exe": "IntellaCmd.exe *",
            "topbar.exe_locked": "(locked via .ini)",
            "topbar.exe_dialog": "IntellaCmd.exe",
            "topbar.language": "Language",
            "topbar.language_restart": "The selected language will apply the next time the application starts.",
            "common.browse": "Browse…",
            "common.yes": "yes",
            "common.no": "no",
            "unit.gb": "GB",
            "unit.mb": "MB",
            "common.filetype_text": "Text",
            "common.filetype_all": "All",
            "journal.export": "Export the log…",
            "journal.clear": "Clear",
            "journal.cleared": "Log cleared.",
            "journal.filetype_log": "Log",
            "journal.exported_log": "Log exported: {p}",
            "journal.exported_msg": "Log exported:\n{p}",
            "journal.export_failed": "Export failed:\n{e}",
            "common.extra_args": "Extra arguments",
            "common.export_csv": "Export as CSV…",
            "common.case_required_title": "Case required",
            "common.fields_required_title": "Required fields",
            "common.exported_to": "Exported:\n{p}",
            "common.export_failed": "Failed:\n{e}",
            "common.export_title": "Export",
            "col.name": "Name",
            "col.type": "Type",
            "col.timezone": "Timezone",
            "col.size": "Size",
            "col.bytes": "Bytes",
            "col.segments": "Segments",
            "col.path": "Path",
            "col.tasks": "Tasks",
            "inventory.case_frame": "Case to inventory",
            "inventory.case_folder": "Case folder",
            "inventory.autolicense": "Auto-select license (-autoSelectFullProcessingLicense)",
            "inventory.run": "Read sources (IntellaCmd)",
            "inventory.scan": "Scan zero-size folders",
            "inventory.export_xml": "Export XML…",
            "inventory.export_tasks": "Export case tasks…",
            "inventory.info_profile": "Profile info →",
            "inventory.no_case": "No case selected.",
            "inventory.pick_case_title": "Intella case folder",
            "inventory.not_a_case": "⚠ Not an Intella case folder (case.xml missing).",
            "inventory.case_folder_title": "Case folder",
            "inventory.xml_unreadable": "⚠ case.xml is unreadable.",
            "inventory.xml_read_failed": "Could not read case.xml:\n{e}",
            "inventory.case_detected_log": "Case detected: « {n} » — created by {u}, {s} used.",
            "inventory.case_detected_summary": "Case « {n} » — {s} used. « Read sources » for deduplication.",
            "inventory.case_required_body": "First select a valid case folder (case.xml detected).",
            "inventory.exe_required": "Set IntellaCmd.exe (above).",
            "inventory.user_required": "User not found in case.xml.",
            "inventory.reading": "Reading in progress…",
            "inventory.reading_log": "Inventory of the case's sources: {c}",
            "inventory.read_failed": "Read failed (see Log).",
            "inventory.read_error_log": "Inventory error: {m}",
            "inventory.sources_title": "Source inventory",
            "inventory.n_sources_read": "{n} source(s) read in the case.",
            "inventory.n_cached_folders": "{n} folder(s) already measured, reused from {f}.",
            "inventory.n_unknown_folders": "{n} folder(s) with no reported size — use « Scan zero-size folders » to measure them.",
            "inventory.cache_applied_log": "{n} zero-size folder(s) reused from cache {f} (total {t}).",
            "inventory.size_mismatch_log": "Size consistency: case.xml {c} < sum of sources {s} (gap {p:.1f}%). Overflow safeguard based on {b}.",
            "inventory.size_mismatch_title": "Size consistency",
            "inventory.size_mismatch_body": "The case's used size (case.xml: {c}) is {p:.1f}% lower than the sum of the sources read ({s}).\n\nSome listed sources may not be (fully) indexed in the case.\n\nAny overflow calculation will use the larger value ({b}).",
            "inventory.case_empty": "Case « {n} » — empty (no source indexed).",
            "inventory.case_summary": "Case « {n} » — {c} source(s) — case size {s}",
            "inventory.n_scannable_folders": "{n} zero-size folder(s) (scannable)",
            "inventory.zero_folders_title": "Zero-size folders",
            "inventory.zero_folders_none": "No folder without size to measure.\nFirst read the case's sources.",
            "inventory.scan_start_log": "Scanning {n} zero-size folder(s)…",
            "inventory.measuring_progress": "Measuring folders… {i}/{n}",
            "inventory.measuring_progress_named": "Measuring folders… {i}/{n}: {f}",
            "inventory.sizes_saved_log": "Sizes saved in {f}.",
            "inventory.folders_measured_log": "Folders measured: {n} — total {t}.",
            "inventory.folders_measured_summary": "{n} folder(s) measured — total {t} (added to the inventory sum).",
            "inventory.default_profile_name": "profile",
            "inventory.info_profile_no_inventory": "First read the case's sources (« Read sources »).",
            "inventory.info_profile_no_selection": "Select a source in the table.",
            "inventory.info_profile_not_found": "Source not found (re-read the sources).",
            "inventory.info_profile_empty": "Source « {n} » exposes no usable setting (indexOptions/domainBoundaries empty).",
            "inventory.info_profile_log": "Profile info: settings from « {n} » transferred to the Profiles tab ({c} option(s)).",
            "inventory.export_xml_none": "No XML available.\nFirst run « Read sources ».",
            "inventory.export_xml_log": "Sources XML exported: {p}",
            "inventory.export_tasks_none": "No task on this case's sources.\nFirst read the sources (« Read sources »).",
            "inventory.export_tasks_log": "Case tasks exported ({n} deduplicated task(s)): {p}",
            "inventory.export_tasks_msg": "{n} deduplicated task(s) exported:\n{p}\n\n1 object = 1 logical task (per-source UUIDs merged by signature).",
            "inventory.export_csv_none": "First read a case's sources.",
            "inventory.export_csv_log": "Inventory exported as CSV: {p}",
            "common.save": "Save",
            "common.delete": "Delete",
            "group.mail": "Mail & e-mails",
            "group.chats": "Chats & conversations",
            "group.archives": "Archives & databases",
            "group.windows": "Windows system",
            "group.browser": "Web & browsers",
            "group.images": "Disk images & recovery",
            "group.vsc": "Volume Shadow Copies (images)",
            "group.text": "Text & analysis",
            "group.filters": "Filters",
            "group.cache": "Cache & advanced",
            "opt.indexMailArchives": "Index mail archives",
            "opt.emailsGeolocationEnabled": "E-mail geolocation",
            "opt.indexChatMessages": "Index chat messages",
            "opt.processingMode": "Chat processing mode",
            "opt.splitMode": "Conversation splitting",
            "opt.numberMessagesPerConversation": "Max messages / conversation",
            "opt.indexArchives": "Index archives (zip, rar…)",
            "opt.indexDatabases": "Index databases",
            "opt.indexWindowsRegistry": "Index Windows registry",
            "opt.indexWindowsEventLog": "Index Windows event logs",
            "opt.indexBrowserHistory": "Index browsing history",
            "opt.recoverDeleted": "Recover deleted files",
            "opt.carveUnallocatedSpace": "Carve unallocated space",
            "opt.verifyAff4Hashes": "Verify AFF4 hashes",
            "opt.indexVolumeShadowCopies": "Index VSS shadow copies",
            "opt.suppressUnchangedFilesInVsc": "Suppress unchanged files (VSS)",
            "opt.preferNewestFilesInVsc": "Prefer newest files (VSS)",
            "opt.indexChangedLastAccessFilesInVsc": "Account for last access (VSS)",
            "opt.indexEmbeddedImages": "Index embedded images",
            "opt.analyseParagraphs": "Analyze paragraphs",
            "opt.indexUnstructured": "Index unstructured content",
            "opt.sourceTypeFilter": "MIME type filter (comma-separated)",
            "opt.sourceTypeFilterMode": "Type filter mode",
            "opt.sourceHashFilters": "Hash lists (.md5, comma-separated)",
            "opt.fileNameFilters": "File name filter",
            "opt.cacheEvidenceFiles": "Cache evidence files",
            "opt.maxBinarySizeToStore": "Max binary size stored",
            "opt.custodian": "Custodian",
            "opt.enableCrawlerScript": "Enable a crawler script",
            "opt.sourceCrawlerScriptType": "Crawler script type",
            "opt.sourceCrawlerScriptFile": "Crawler script file",
            "profiles.intro": "A profile is a set of analysis settings applied to a source at import time (assigned in the « 2. Import » tab, « Profile » column). The « default » profile applies Intella's default settings (no option forced). Only values that differ from the default are saved and emitted.",
            "profiles.saved": "Saved profiles",
            "profiles.name_label": "Profile name",
            "profiles.new": "New",
            "profiles.rename": "Rename…",
            "profiles.comments": "Comments",
            "profiles.analysis_options": "Analysis options",
            "profiles.to_verify": "to verify",
            "profiles.images_only": "[images]",
            "profiles.filename_filter_tip": "Wildcards allowed in file names: « ? » (one character) and « * » (several). E.g.: report_*.pdf, IMG_????.jpg",
            "profiles.name_required": "Enter a profile name.",
            "profiles.default_reserved": "The « default » profile is reserved.",
            "profiles.overwrite_confirm": "Profile « {n} » already exists. Update it?",
            "profiles.saved_log": "Profile saved: « {n} ».",
            "profiles.saved_msg": "Profile « {n} » saved.",
            "profiles.select_non_default": "Select a profile (≠ « default »).",
            "profiles.rename_title": "Rename the profile",
            "profiles.new_name": "New name:",
            "profiles.renamed_log": "Profile renamed: « {o} » → « {n} ».",
            "profiles.delete_confirm": "Delete profile « {n} »?",
            "profiles.deleted_log": "Profile deleted: « {n} ».",
            "profiles.err_name_empty": "The profile name is empty.",
            "profiles.err_default_reserved": "The « default » profile is reserved and cannot be edited.",
            "profiles.err_default_no_delete": "The « default » profile cannot be deleted.",
            "profiles.err_default_reserved_short": "The « default » profile is reserved.",
            "profiles.err_new_name_empty": "The new name is empty.",
            "profiles.err_not_found": "Profile not found: {n}",
            "profiles.err_already_exists": "A profile « {n} » already exists.",
            "tabs.inventory": "1. Case inventory",
            "tabs.detail": "Case details",
            "tabs.import": "2. Import",
            "tabs.profiles": "Profiles",
            "tabs.journal": "Log",
            "tabs.help": "Help",
            "detail.no_case": "Select a case in the « 1. Case inventory » tab.",
            "detail.h1_case": "Case",
            "detail.name": "Name",
            "detail.folder": "Folder",
            "detail.description": "Description",
            "detail.id": "ID",
            "detail.created": "Created on",
            "detail.last_opened": "Last opened",
            "detail.created_by": "Created by",
            "detail.size": "Size used",
            "detail.size_value": "{h}  ({b:,} bytes)",
            "detail.version": "Version (original / current)",
            "detail.h1_prefs": "Case preferences",
            "detail.optim_folder": "Optimization folder",
            "detail.authorized_users": "Authorized users",
            "detail.email_threading": "Email threading done",
            "detail.saved_searches": "Saved searches done",
            "detail.hash_algo": "Message hashing algorithm",
            "detail.h1_tasks2": "Post-indexing tasks (tasks2.json)",
            "detail.no_tasks2": "No post-indexing task declared.",
            "import.already_used": "already {s} used",
            "import.and_n_more": "… and {n} more.",
            "import.auto_removed_log": "{n} source(s) already indexed, removed automatically.",
            "import.case_label": "Case:",
            "import.case_prefix": "Case « {n} » : ",
            "import.case_tasks": "Case tasks (inventory)",
            "import.case_tasks_none": "No task is defined on this case's sources.",
            "import.case_tasks_not_loaded": "The case's source list is not loaded.\nRun « Read sources » in the « 1. Case inventory » tab.",
            "import.case_tasks_recycled_log": "Tasks recycled from the case inventory: {n} task(s).",
            "import.case_tasks_recycled_msg": "{n} case task(s) loaded (deduplicated).\nThey apply like a task file: check them per source.",
            "import.case_tasks_unreadable": "Unreadable tasks:\n{e}",
            "import.check_all": "Imp.: check all",
            "import.close": "Close",
            "import.col_delete": "Del.",
            "import.col_import": "Imp.",
            "import.col_import_log": "Import log",
            "import.col_in_case": "In the case",
            "import.col_name": "Source name",
            "import.col_profile": "Profile",
            "import.col_source": "Source",
            "import.compute_size": "Compute size",
            "import.computing_missing_sizes_log": "Computing missing sizes (checked sources) before generation…",
            "import.computing_size_log": "Computing the size of {n} checked source(s)…",
            "import.corrections_needed": "Corrections needed",
            "import.default_profile_label": "Default profile:",
            "import.empty": "empty",
            "import.empty_selection_body": "Check at least one source in the « Imp. » (Import) column.",
            "import.empty_selection_title": "Empty selection",
            "import.export_list": "Export the list…",
            "import.folders_panel": "Standard folders (FOLDER_OR_FILE) — 1 path/line",
            "import.generate": "Generate the import files",
            "import.generate_anyway": "Generate anyway?",
            "import.images_panel": "Forensic images (DISK_IMAGE) — 1 path/line",
            "import.import_list": "Import a list…",
            "import.integrity_check_log": "Source integrity verification: ",
            "import.integrity_disabled_log": "DISABLED (« {a} » added to the arguments).",
            "import.integrity_enabled_log": "enabled (argument removed).",
            "import.integrity_title": "Source integrity",
            "import.inventory_exceeds": "(inventory sum > case.xml {s})",
            "import.launch_failed_log": "Failed to launch the import: {e}",
            "import.launch_impossible": "Cannot launch:\n{e}",
            "import.launched_log": "Import launched: {b}",
            "import.limit_exceeded_body": "The {lim:g} GB limit would be exceeded.\n\n{n} source(s) ({v}) were UNCHECKED (the part that fits stays checked):\n{list}\n\nNothing was generated. Check/adjust the « Imp. » boxes, then run « Generate » again to import what you kept.\n\nFor the rest: create the sub-case manually in Intella, target it, re-check and re-import.",
            "import.limit_exceeded_log": "Limit exceeded: {n} source(s) unchecked ({v}). Generation suspended — adjust the checkboxes then run « Generate » again.",
            "import.limit_exceeded_title": "Limit reached — generation suspended",
            "import.limit_label": "Limit / case (GB)",
            "import.limit_status": "{etat} the limit ({eff} / {lim})",
            "import.list_imported_log": "Summary imported: {n} source(s) from {p}",
            "import.list_imported_removed": "({n} already in the case, removed).",
            "import.list_invalid_format": "Invalid format (a list of sources was expected).",
            "import.list_replace_confirm": "Replace the current summary ({cur} source(s)) with {new} source(s) from the file?",
            "import.list_unreadable": "Could not read:\n{e}",
            "import.location_label": "Location:",
            "import.log_failed": "FAILED: {m}",
            "import.log_ok": "OK",
            "import.n_indexed": "{n} source(s) indexed",
            "import.n_removed_auto": "{n} already indexed in the case, removed automatically.",
            "import.n_sources_loaded": "{n} source(s) loaded.",
            "import.no_bat_found": "No import file found for this case.\nFirst click « Generate the import files ».",
            "import.no_case_selected": "ⓘ No case selected — choose one in the « 1. Case inventory » tab.",
            "import.no_checked": "No source checked « Import ».\nOnly checked rows are measured.",
            "import.no_inventory_read": "⚠ source list not read (tab 1) → no deduplication.",
            "import.no_rows_to_export": "No row to export.",
            "import.over_limit": "⚠ exceeds",
            "import.partial": "(partial)",
            "import.profile_applied_all_log": "Profile « {p} » applied to all sources ({n}).",
            "import.recap_empty": "The summary is empty.",
            "import.recap_exported_log": "Summary exported ({n} source(s)): {p}",
            "import.recap_exported_msg": "{n} source(s) exported:\n{p}",
            "import.recap_frame": "Source summary",
            "import.reload_tasks": "Reload tasks",
            "import.report_done": "Generation complete — {n} source(s) imported.",
            "import.report_existing": "Already in the case: {e}  →  total {t}.",
            "import.report_folder": "Folder: {d}",
            "import.report_new_volume": "New sources volume: {v}.",
            "import.report_no_subcase": "No sub-case is created automatically: create it manually in Intella then re-import the rest.",
            "import.report_open_folder": "Open the scripts folder?",
            "import.report_over_limit": "⚠ The total exceeds the {lim:g} GB limit by {ov}.",
            "import.report_oversized": "⚠ Single source(s) > limit (cannot be split): {n}",
            "import.report_resilient": "Resilient import: 1 command per source, 1 log per source.",
            "import.report_run_logs": "Logs for this run: logs\\{r}\\ (« Validate operations » will read this run).",
            "import.report_single_case": "A single case (under the limit).",
            "import.report_title": "Done",
            "import.run_confirm": "Run the import into Intella?\n\n{b}\n\nIntellaCmd will add the sources to the case (not reversible on the case side). A console window opens and shows progress.\n\nContinue?",
            "import.run_import": "Import (run the .bat)",
            "import.select_case_first": "First select a case (« 1. Case inventory » tab).",
            "import.select_case_short": "First select a case (« 1. Case inventory » tab).",
            "import.select_case_target": "First select a case in the « 1. Case inventory » tab.",
            "import.size_done_log": "Size computation done. Total checked: {t}.",
            "import.size_title": "Size",
            "import.skip_integrity": "Do not verify source integrity (multi-segment images — works around the Vound bug)",
            "import.source_removed_log": "Source removed from the summary: {n}",
            "import.summarize": "▼ Summarize",
            "import.summary_log": "Summary: {n} source(s).",
            "import.summary_removed_log": "{n} already in the case, removed.",
            "import.target_case_frame": "Target case (set by the « 1. Case inventory » tab)",
            "import.tasks_check_all": "Tasks: check all",
            "import.tasks_file_label": "Task file",
            "import.tasks_file_loaded_log": "Task file loaded: {n} task(s).",
            "import.tasks_file_not_found": "Not found:\n{p}",
            "import.tasks_file_read_error_log": "Error reading the task file: {e}",
            "import.tasks_file_title": "Task file",
            "import.tasks_file_unavailable_log": "Task file unavailable (field cleared or file missing): using the definitions already loaded in memory.",
            "import.tasks_file_unreadable": "Could not read:\n{e}",
            "import.tasks_uncheck_all": "Tasks: uncheck all",
            "import.timezone_label": "Timezone",
            "import.total_summary": "{n} source(s), {c} to import — checked size: {t}{suffix}",
            "import.uncheck_all": "Imp.: uncheck all",
            "import.under_limit": "under",
            "import.validate": "Validate operations",
            "import.validate_absent": "  ✗ {n}: absent from the case (no matching import log).",
            "import.validate_failed": "  ✗ {n}: failed — {m}",
            "import.validate_head": "Case « {c} » : {n} source(s) present.  Out of {v} checked: {ok} in the case, {ko} absent.  {l} log(s) analyzed.",
            "import.validate_other": "  • {n} : {m}",
            "import.validate_present": "  ✔ {n}: present in the case.",
            "import.validate_requires": "IntellaCmd.exe and the user are required.",
            "import.validate_rescan_failed_log": "Validation: re-scan failed: {m}",
            "import.validate_run_analyzed": "  Run analyzed: {r}.",
            "import.validate_run_suffix": " (run {r})",
            "import.validate_start_log": "Validating operations: re-scanning the case + analyzing logs…",
            "import.validate_summary_log": "Validation{r} : {n} source(s) in the case, {l} log(s) analyzed.",
            "import.validation_exported_log": "Validation exported as CSV: {p}",
            "import.warnings_title": "Warnings",
            "import.write_title": "Writing",
            "import.zero_sources": "0 source",
            "type.folder": "Folder",
            "type.image": "Image",
            "validation.case_location_required": "The case location is required.",
            "validation.exe_not_found": "IntellaCmd.exe not found: {p}",
            "validation.exe_required": "The IntellaCmd.exe path is required.",
            "validation.no_sources": "No source. Paste paths then click « Summarize ».",
            "validation.non_first_segment": "Image segment may not be the first one (point to the 1st, .E01): {p}",
            "validation.output_dir_required": "The output folder is required.",
            "validation.path_not_absolute": "Path not absolute (IntellaCmd requires absolute paths): {p}",
            "validation.path_not_found": "Path not found: {p}",
            "validation.tasks_unreadable": "Tasks are checked but the task file could not be read.",
            "validation.user_required": "The « User » field is required.",
            "import.size_cache_reused_log": "{n} source(s) already measured, reused from cache (IF_<case>.info).",
            "task_builder.err_not_array": "Tasks must be a JSON array (format exported by Intella).",
            "task_builder.default_task_name": "Task {n}",
            "case_meta.err_no_case_xml": "case.xml not found at this location. Make sure you are pointing to an Intella case folder.",
            "op_validation.log_unreadable": "Unreadable log: {e}",
            "op_validation.added_but": "Added OK but: {m}",
            "op_validation.no_confirmation": "No confirmation of addition in the log."
        },
        "help": [
            [
                "h1",
                "IntellaFeeder — Help"
            ],
            [
                "p",
                "This tool prepares the automatic import of sources into an existing Intella case, without going through the web wizard. You paste lists of paths, choose which extra tasks to run, and the tool generates the files and a ready-to-run « .bat » script."
            ],
            [
                "h1",
                "Recommended workflow"
            ],
            [
                "b",
                "1. « Case inventory » tab: first read the sources already present in the case. This tells you how much space is already used and flags sources already indexed (so you don't add them twice). The « Export XML » button saves a copy of the list that was read."
            ],
            [
                "b",
                "2. « Import » tab: paste the paths of the new sources (1 path per line) — forensic images on the left, folders/files on the right."
            ],
            [
                "b",
                "3. Click « Summarize »: the table lists the sources. Sources already present in the case (per the inventory) are highlighted."
            ],
            [
                "b",
                "4. Click « Compute size » to know the volume of the sources. This step is OPTIONAL: by default the tool already uses the used-size value declared in the case's case.xml file (fetched in the « 1. Case inventory » tab). But that figure does not count sources already referenced in Intella as long as they haven't been indexed yet (a source added to a case can stay pending indexing) — so it may underestimate the actual volume used. « Compute size » measures the checked new sources directly on disk, for a more reliable safeguard if you are close to the limit. Each measurement is saved to a file created at the root of the case folder (IF_<case name>.info): a source already measured in a previous session is not rescanned."
            ],
            [
                "b",
                "5. For each source, check the extra tasks to run (columns T1, T2…)."
            ],
            [
                "b",
                "6. Click « Generate »: the tool writes the output files and the « .bat » script(s). Run the « .bat » to perform the import into Intella."
            ],
            [
                "h1",
                "Interface tips"
            ],
            [
                "b",
                "Real name of a task: hover over a T1, T2… column header (or its ✓ / ✗ buttons) to see the task's full name."
            ],
            [
                "b",
                "Sorting: click a column header to sort (an ▲ / ▼ arrow shows the direction). Click again to reverse the sort."
            ],
            [
                "b",
                "Horizontal scrolling: the bottom scrollbar lets you see all task columns when there are many."
            ],
            [
                "b",
                "Rename a source: double-click its name in the table. This only changes the LABEL displayed in Intella (the source's name) — the actual path being integrated (the file/folder it points to) is not changed: the original source is imported normally. Useful for giving a more readable name than a technical file name, without changing anything about what gets indexed."
            ],
            [
                "b",
                "Quick check/uncheck: « Check all / Uncheck all », or the « T1 ✓ / T1 ✗ » buttons to (un)check a whole column at once."
            ],
            [
                "b",
                "Quotes: you can paste paths surrounded by quotes, they are cleaned up automatically."
            ],
            [
                "b",
                "Multi-segment images (.E01/.E02… or .ad1/.ad2…): only enter the FIRST segment; the others are picked up automatically."
            ],
            [
                "h1",
                "Analysis-parameter profiles"
            ],
            [
                "p",
                "A « profile » groups indexing settings (mail, archives, deleted-file recovery, filters…) that you apply to a source at import time. Profiles are created in the « Profiles » tab and are shared across your cases."
            ],
            [
                "b",
                "In the « Profiles » tab: pick a profile from the list to see its options, or click « New » to start from the defaults. Check the options you want, give it a name, then « Save »."
            ],
            [
                "b",
                "The « default » profile applies Intella's standard settings: it forces no option and cannot be edited."
            ],
            [
                "b",
                "« Profile info » tip: set up a sample source in Intella, then in the « Case inventory » tab read the sources, select that source and click « Profile info → ». Its settings (including the type filter) automatically fill in the Profiles tab: all that's left is to name and save the profile."
            ],
            [
                "b",
                "Each profile is saved as a file in the « profils » folder (next to the program); you can back them up or share them. The « Comments » field (at the top) lets you note what the profile is for."
            ],
            [
                "b",
                "File name filter: you can use the wildcards « ? » (one character) and « * » (several characters), e.g. report_*.pdf."
            ],
            [
                "b",
                "MIME type filter: it's a long list; the box grows when you click inside it, to make copy/paste easier."
            ],
            [
                "b",
                "In the Import tab's summary table, the « Profile » column lets you choose the profile for each source. The « Default profile » menu applies the chosen profile to every row at once."
            ],
            [
                "h1",
                "MIME types for the type filter"
            ],
            [
                "p",
                "The « MIME type filter » field expects a comma-separated list, combined with either « include » or « exclude » mode. This list mixes TWO levels that coexist:"
            ],
            [
                "b",
                "Intella CATEGORIES (« category/… »): real thematic groupings defined by Intella. Checking a category selects all the formats it contains at once."
            ],
            [
                "b",
                "INDIVIDUAL TYPES (« application/x-pdf », « application/rtf »…): one precise format, checked on its own, independently of its category."
            ],
            [
                "p",
                "An individual type is therefore NOT « contained » in a « category/… » entry in the list: the two are chosen separately. Example: application/x-pdf belongs thematically to Documents, but is checked on its own (Intella does not nest them). The exact list depends on your case — the most reliable approach is to use « Profile info » on a source configured in Intella."
            ],
            [
                "h2",
                "Intella categories (the real categories)"
            ],
            [
                "pcsv",
                "category/accounts, category/browser_cookies, category/browser_downloads, category/chat, category/contacts, category/containers, category/crypto_currency, category/formulas, category/graphics, category/hangul_document, category/launched_programs, category/media, category/other_communications, category/other_documents, category/other_media, category/others, category/presentations, category/recently_accessed_files, category/scheduling, category/system, category/user_activity, category/user_sessions, category/video, category/voice, category/word_processing"
            ],
            [
                "h2",
                "Individual types (precise formats)"
            ],
            [
                "p",
                "These are NOT Intella categories. The thematic grouping below is ours, only to make reading easier."
            ],
            [
                "bcsv",
                "Word processing & office: application/rtf, text/rtf, application/x-pdf, application/msonenote, application/vnd.fdf, application/vnd.framemaker, application/x-framemaker, application/vnd.ms-publisher, application/vnd.ms-xpsdocument, application/vnd.oasis.opendocument.text (and -master, -template, -web), application/vnd.stardivision.writer (and -global), application/vnd.stardivision.math, application/vnd.stardivision.draw, application/vnd.sun.xml.writer (and .template), application/vnd.wordperfect, application/wps-office.wps/.wpt/.dpt/.ett, application/x-mspowerpoint, text/vnd.wap.wml"
            ],
            [
                "bcsv",
                "Images, video & media: image/iff, image/x-iff, application/iff, application/x-iff, application/ogg, application/riff, application/x-iso-base-media, application/x-shockwave-flash, video/x-ms-asf, video/x-ms-wm"
            ],
            [
                "bcsv",
                "Archives & containers: application/binhex, application/unix-v7-tar, application/x-java-webarchive, application/x-rar-compressed-v5, application/x-sitx"
            ],
            [
                "bcsv",
                "Windows & forensic artifacts (Intella): application/vnd.ms-registry, application/vnd.ms-registry-key, application/vnd.ms-windows-xml-event-log-entry, application/x-intella-windows-registry-artifacts, application/x-intella-windows-shellbag, application/x-intella-windows-10-timeline-entry, application/x-intella-windows-push-notification-entry, application/x-intella-operating-system-information, application/x-intella-startup-program, application/x-intella-installed-application, application/x-intella-time-zone-information, application/x-intella-usb-storage-device, application/x-intella-boot-sector-file, application/x-intella-net-connection, application/x-intella-device-acquisition, application/x-intella-aws-s3-bucket, application/x-intella-imap-connection, application/x-intella-sharepoint-post"
            ],
            [
                "bcsv",
                "Network & e-mail: application/pcap, application/vnd.tcpdump.pcap, message/rfc822-headers, application/applefile, multipart/appledouble"
            ],
            [
                "h1",
                "Multi-segment images: integrity"
            ],
            [
                "p",
                "A known issue in the vendor's software (Vound) can cause integrity verification to fail for forensic images split into several files. Until a fix is released, the Import tab offers a « Do not verify source integrity » checkbox."
            ],
            [
                "b",
                "When checked, the « -validateDiskImage false » option is automatically added to the « Extra arguments » field: the import no longer performs integrity verification. The setting is remembered per case."
            ],
            [
                "h1",
                "Avoiding double indexing"
            ],
            [
                "p",
                "After reading a case's inventory, the Import tab compares the paths you paste with those already indexed. Sources already present are automatically removed from the summary table (both when clicking « Summarize » and when importing a list)."
            ],
            [
                "h1",
                "When the case gets too big"
            ],
            [
                "p",
                "An Intella case is capped for safety (950 GB here, out of the 1 TB allowed). The tool adds up the volume already in the case and that of the new sources:"
            ],
            [
                "b",
                "If the total stays under the limit: a single import, into the existing case."
            ],
            [
                "b",
                "If the total exceeds the limit: the tool WARNS, automatically unchecks the last sources so only what fits remains, and SUSPENDS generation (nothing is written). No sub-case is created automatically."
            ],
            [
                "b",
                "What to do: check/adjust the « Imp. » checkboxes then run « Generate » again to import what you kept. For the rest: create the sub-case manually in Intella, target it as the case, re-check and re-import the remaining sources."
            ],
            [
                "b",
                "The « Imp. » column (checkbox) selects which sources are measured and imported; the « ✕ » cross removes a row from the summary. The « Export / Import a list » buttons save the state of the summary table."
            ],
            [
                "b",
                "A single source larger than the limit cannot be imported as-is: it is flagged."
            ],
            [
                "p",
                "Note: the volume of « folder » sources is not always known from the inventory; in that case the displayed total is marked « partial » and the decision may be optimistic. Check these folders if you are close to the limit."
            ],
            [
                "h1",
                "Language files"
            ],
            [
                "p",
                "The « lang » folder (next to the program) contains the FR.lang and US.lang files. These files are OPTIONAL: French and English are already built into the application (hard-coded), so it runs normally even without this folder. They can be used as a template to create a translation into another language."
            ]
        ]
    }
}
