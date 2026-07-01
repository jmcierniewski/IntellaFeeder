"""Lecture du fichier de tâches et génération des fichiers par combinaison.

Le fichier de tâches (exporté d'Intella) est un tableau JSON ; chaque tâche est
RÉUTILISÉE telle quelle (réglages et UUID inchangés). Le nombre de tâches est
dynamique : une colonne sera créée par tâche dans l'UI. Pour chaque source, le
``taskFile`` pointe vers un fichier contenant le sous-ensemble de tâches cochées.
"""

import json
import os

import i18n


def write_json(data, path: str) -> None:
    """Écrit ``data`` en JSON (ASCII échappé, sûr quel que soit l'encodage lu)."""
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=True, indent=2)


def tasks_from_objs(data) -> list:
    """Construit la liste ``{"id","name","obj"}`` depuis une liste d'objets tâche.

    ``id`` retombe sur le nom puis l'index si absent. Lève ``ValueError`` si la
    structure n'est pas une liste.
    """
    if not isinstance(data, list):
        raise ValueError(i18n.t(
            "task_builder.err_not_array",
            "Les tâches doivent être un tableau JSON (format exporté par Intella)."
        ))
    tasks = []
    for i, obj in enumerate(data):
        if not isinstance(obj, dict):
            continue
        tid = obj.get("id") or obj.get("name") or f"task_{i}"
        name = obj.get("name") or i18n.t("task_builder.default_task_name", "Tâche {n}", n=i + 1)
        tasks.append({"id": tid, "name": name, "obj": obj})
    return tasks


def load_tasks(tasks_path: str) -> list:
    """Charge toutes les tâches du fichier, dans l'ordre (cf. ``tasks_from_objs``)."""
    with open(tasks_path, "r", encoding="utf-8") as f:
        data = json.load(f)
    return tasks_from_objs(data)


def build_combo_files(tasks: list, combos, output_dir: str) -> dict:
    """Écrit un fichier de tâche par combinaison de tâches utilisée.

    ``tasks``  : liste {id,name,obj} (ordre du fichier).
    ``combos`` : itérable de frozenset d'ids de tâches (combinaisons présentes).
    Retourne ``{frozenset(ids): chemin_absolu}``. Les tâches sont écrites dans
    l'ordre du fichier ; le nom de fichier reflète les positions (T1, T2…).
    """
    output_dir = os.path.abspath(output_dir)
    index_of = {t["id"]: i for i, t in enumerate(tasks)}
    result: dict = {}
    for combo in combos:
        indices = sorted(index_of[i] for i in combo if i in index_of)
        if not indices:
            continue
        objs = [tasks[i]["obj"] for i in indices]
        label = "_".join(f"T{i + 1}" for i in indices)
        path = os.path.join(output_dir, f"task_{label}.json")
        write_json(objs, path)
        result[frozenset(combo)] = path
    return result
