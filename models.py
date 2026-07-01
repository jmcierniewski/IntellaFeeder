"""Structures de données métier."""

from dataclasses import dataclass, field


@dataclass
class Source:
    """Une source forensique à importer dans Intella.

    name        : nom affiché de la source (dérivé du basename, éditable).
    path        : chemin absolu de la preuve (fichier image ou dossier).
    source_type : DISK_IMAGE ou FOLDER_OR_FILE (voir config).
    selected_task_ids : ids des tâches (du fichier de tâches) cochées pour cette
                        source. Le nombre de tâches est dynamique.
    size_bytes  : taille calculée (octets) ; None tant que non calculée.
    import_selected : si True, la source est incluse dans le calcul de taille et
                      la génération d'import ; sinon ignorée (laissée pour un lot
                      ultérieur / un sous-cas créé manuellement).
    profile     : nom du profil de paramètres d'analyse appliqué à cette source
                  (« défaut » = options omises = défauts Intella).
    """

    name: str
    path: str
    source_type: str
    selected_task_ids: set = field(default_factory=set)
    size_bytes: int | None = None
    import_selected: bool = True
    profile: str = "défaut"
