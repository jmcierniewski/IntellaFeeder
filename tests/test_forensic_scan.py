"""Collecte des images forensiques d'un dossier (panneau « Images forensiques »).

Ce module remplace l'outil externe qui produisait les listes de chemins : ses
deux erreurs possibles coûtent cher et se découvrent tard, d'où ces tests.

- **Ajouter ce qui n'est pas une image** (un rapport, une photo) : la source
  part à l'import et Intella ne permet pas de revoir ses réglages ensuite.
- **Ajouter un segment non initial** (`.E02`, `.ad2`) : l'import de cette source
  échoue, ou pire, une image de 40 segments produit 40 lignes.
"""

import io
import os

import pytest

import forensic_scan as fs


def touch(folder, *names):
    os.makedirs(folder, exist_ok=True)
    for n in names:
        with io.open(os.path.join(folder, n), "w", encoding="utf-8") as f:
            f.write("x")


class TestImageKind:
    @pytest.mark.parametrize("name,kind", [
        ("scelle.E01", ".e01"), ("scelle.e01", ".e01"),
        ("scelle.Ex01", ".ex01"), ("scelle.L01", ".l01"), ("scelle.Lx01", ".lx01"),
        ("scelle.s01", ".s01"), ("scelle.ad1", ".ad1"),
        ("image.dd", ".dd"), ("disque.vhd", ".vhd"), ("disque.vhdx", ".vhdx"),
        ("disque.vmdk", ".vmdk"), ("brut.001", ".001"),
    ])
    def test_premiers_segments_retenus(self, name, kind):
        assert fs.image_kind(name) == kind

    @pytest.mark.parametrize("name", [
        "scelle.E02", "scelle.e15", "scelle.eaa",     # EWF, suite
        "scelle.Ex02", "scelle.L02", "scelle.Lx02", "scelle.s02",
        "scelle.ad2", "scelle.ad28", "brut.002",
    ])
    def test_segments_suivants_refuses(self, name):
        assert fs.image_kind(name) == ""
        assert fs.refusal_reason(name) == fs.REASON_SEGMENT

    @pytest.mark.parametrize("name", [
        "rapport.pdf", "photo.jpg", "notes.txt", "liste.csv", "sans_extension",
        "scelle.E01.bak",
    ])
    def test_autres_fichiers_refuses(self, name):
        assert fs.image_kind(name) == ""
        assert fs.refusal_reason(name) == fs.REASON_UNKNOWN

    @pytest.mark.parametrize("name", [
        "disque-s001.vmdk", "disque-flat.vmdk", "disque-delta.vmdk", "disque-ctk.vmdk",
    ])
    def test_annexes_vmdk_refusees(self, name):
        """Un VMDK découpé n'a qu'un descripteur à ouvrir ; ses tronçons ne se
        donnent jamais à IntellaCmd."""
        assert fs.image_kind(name) == ""
        assert fs.refusal_reason(name) == fs.REASON_VMDK_PART


class TestScanFolder:
    def _arbre(self, tmp_path):
        racine = str(tmp_path / "scelles")
        touch(racine, "rapport.pdf", "SCELLE_01.ad1", "SCELLE_01.ad2")
        touch(os.path.join(racine, "sous", "encore"), "SCELLE_02.E01",
              "SCELLE_02.E02", "SCELLE_02.E03", "photo.jpg")
        return racine

    def test_non_recursif_par_defaut(self, tmp_path):
        """Choix du 07/09/2026 : on s'arrête aux fichiers du dossier désigné.

        Descendre d'office ramènerait les images des cas voisins ou des copies
        de travail rangées sous le même dossier — erreur invisible jusqu'après
        l'indexation.
        """
        found, counts = fs.scan_folder(self._arbre(tmp_path))
        assert [os.path.basename(p) for p in found] == ["SCELLE_01.ad1"]
        assert counts == {".ad1": 1}

    def test_recursif_sur_demande(self, tmp_path):
        found, counts = fs.scan_folder(self._arbre(tmp_path), recursive=True)
        noms = sorted(os.path.basename(p) for p in found)
        assert noms == ["SCELLE_01.ad1", "SCELLE_02.E01"]
        assert counts == {".ad1": 1, ".e01": 1}

    def test_une_ligne_par_image_multi_segments(self, tmp_path):
        """40 segments = 1 source : c'est tout l'intérêt du panneau."""
        racine = str(tmp_path / "gros")
        touch(racine, *[f"IMG.E{i:02d}" for i in range(1, 41)])
        found, counts = fs.scan_folder(racine)
        assert len(found) == 1 and counts == {".e01": 1}

    def test_chemins_absolus(self, tmp_path):
        racine = str(tmp_path / "abs")
        touch(racine, "A.ad1")
        (found, _c) = fs.scan_folder(racine)
        assert os.path.isabs(found[0]) and os.path.isfile(found[0])

    def test_dossier_vide(self, tmp_path):
        racine = str(tmp_path / "vide")
        os.makedirs(racine)
        assert fs.scan_folder(racine) == ([], {})

    def test_interruption_rend_ce_qui_est_trouve(self, tmp_path):
        """Un parcours réseau peut durer : l'annulation garde la récolte."""
        racine = str(tmp_path / "lot")
        for i in range(4):
            touch(os.path.join(racine, f"sous{i}"), f"S{i}.ad1")
        vus = []

        def stop():
            return len(vus) >= 2

        def progress(dossiers, images, courant):
            vus.append(courant)

        found, _counts = fs.scan_folder(racine, on_progress=progress,
                                        should_stop=stop, recursive=True)
        assert 0 < len(found) < 4

    def test_progression_appelee(self, tmp_path):
        racine = str(tmp_path / "p")
        touch(racine, "A.ad1")
        appels = []
        fs.scan_folder(racine, on_progress=lambda d, i, c: appels.append((d, i)))
        assert appels and appels[-1][1] == 1


class TestClassifyPaths:
    def test_tri_dossiers_images_refuses(self, tmp_path):
        d = tmp_path / "dossier"
        d.mkdir()
        touch(str(tmp_path), "A.ad1", "rapport.pdf", "B.E02")
        dossiers, images, refuses = fs.classify_paths([
            str(d), str(tmp_path / "A.ad1"), str(tmp_path / "rapport.pdf"),
            str(tmp_path / "B.E02"),
        ])
        assert dossiers == [str(d)]
        assert [os.path.basename(p) for p in images] == ["A.ad1"]
        assert [(os.path.basename(p), r) for p, r in refuses] == [
            ("rapport.pdf", fs.REASON_UNKNOWN),
            ("B.E02", fs.REASON_SEGMENT),
        ]

    def test_racine_de_lecteur_reste_un_dossier(self, tmp_path):
        """« C:\\ » ne doit pas perdre son antislash en route."""
        dossiers, _i, _r = fs.classify_paths([str(tmp_path) + os.sep])
        assert dossiers == [str(tmp_path) + os.sep]


class TestSummarize:
    def test_ordre_decroissant(self):
        assert fs.summarize_counts({".e01": 2, ".ad1": 9}) == "9 × .ad1, 2 × .e01"

    def test_vide(self):
        assert fs.summarize_counts({}) == ""
