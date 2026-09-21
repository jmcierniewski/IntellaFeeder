"""Fichier de tâches : lecture dynamique et 1 fichier par combinaison cochée.

Contrat fort : les tâches sont réutilisées **verbatim** (réglages ET UUID
inchangés), sinon Intella ne les reconnaît pas d'un cas à l'autre.
"""

import json
import os

import pytest

import task_builder


TACHES = [
    {"id": "uuid-1", "name": "OCR", "conditions": ["OCR_PROSPECTS_CONDITION"]},
    {"id": "uuid-2", "name": "Hachage", "extra": {"algo": "MD5"}},
    {"id": "uuid-3", "name": "Threading"},
]


class TestTasksFromObjs:
    def test_id_et_nom(self):
        tasks = task_builder.tasks_from_objs(TACHES)
        assert [t["id"] for t in tasks] == ["uuid-1", "uuid-2", "uuid-3"]
        assert tasks[0]["name"] == "OCR"

    def test_repli_sur_le_nom_puis_index(self):
        tasks = task_builder.tasks_from_objs([{"name": "SansId"}, {}])
        assert tasks[0]["id"] == "SansId"
        assert tasks[1]["id"] == "task_1"

    def test_objet_verbatim(self):
        tasks = task_builder.tasks_from_objs(TACHES)
        assert tasks[1]["obj"] is TACHES[1]

    def test_entrees_non_dict_ignorees(self):
        assert len(task_builder.tasks_from_objs([{"id": "a"}, "bruit", 42])) == 1

    def test_structure_invalide(self):
        with pytest.raises(ValueError):
            task_builder.tasks_from_objs({"pas": "un tableau"})


class TestLoadTasks:
    def test_lecture_fichier(self, tmp_path):
        p = tmp_path / "tasks.json"
        p.write_text(json.dumps(TACHES), encoding="utf-8")
        assert len(task_builder.load_tasks(str(p))) == 3

    def test_format_tasks2_compatible(self, tmp_path):
        """tasks2.json (tâches post-indexation) = même format, exportable tel quel."""
        p = tmp_path / "tasks2.json"
        p.write_text(json.dumps([{"id": "u", "name": "Post"}]), encoding="utf-8")
        assert task_builder.load_tasks(str(p))[0]["name"] == "Post"


class TestBuildComboFiles:
    def test_un_fichier_par_combinaison(self, tmp_path):
        tasks = task_builder.tasks_from_objs(TACHES)
        combos = [frozenset({"uuid-1"}), frozenset({"uuid-1", "uuid-3"})]
        res = task_builder.build_combo_files(tasks, combos, str(tmp_path))
        assert len(res) == 2
        assert os.path.basename(res[frozenset({"uuid-1"})]) == "task_T1.json"
        assert os.path.basename(res[frozenset({"uuid-1", "uuid-3"})]) == "task_T1_T3.json"

    def test_contenu_verbatim_et_ordre_du_fichier(self, tmp_path):
        tasks = task_builder.tasks_from_objs(TACHES)
        combo = frozenset({"uuid-3", "uuid-1"})     # ordre de cochage inversé
        path = task_builder.build_combo_files(tasks, [combo], str(tmp_path))[combo]
        with open(path, encoding="utf-8") as f:
            contenu = json.load(f)
        assert contenu == [TACHES[0], TACHES[2]]    # ordre du fichier source

    def test_combinaison_vide_ignoree(self, tmp_path):
        tasks = task_builder.tasks_from_objs(TACHES)
        assert task_builder.build_combo_files(tasks, [frozenset()], str(tmp_path)) == {}

    def test_ids_inconnus_ignores(self, tmp_path):
        tasks = task_builder.tasks_from_objs(TACHES)
        combo = frozenset({"uuid-1", "uuid-inexistant"})
        path = task_builder.build_combo_files(tasks, [combo], str(tmp_path))[combo]
        assert os.path.basename(path) == "task_T1.json"

    def test_json_ascii_echappe(self, tmp_path):
        """ensure_ascii=True : les accents partent en \\uXXXX (contrat projet)."""
        tasks = task_builder.tasks_from_objs([{"id": "a", "name": "Tâche accentuée"}])
        combo = frozenset({"a"})
        path = task_builder.build_combo_files(tasks, [combo], str(tmp_path))[combo]
        with open(path, encoding="utf-8") as f:
            brut = f.read()
        assert "\\u00e2" in brut and "Tâche" not in brut
