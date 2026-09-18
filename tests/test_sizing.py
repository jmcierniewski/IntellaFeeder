"""Mesure des tailles : dossiers récursifs, images multi-segments, garde-fou.

Enjeu métier : ces valeurs alimentent le contrôle de la limite du cas (950 Go).
Une image multi-segments comptée sur son seul 1ᵉ segment sous-estimerait
massivement le volume.
"""

import os

import pytest

import config
import models
import sizing
from conftest import make_file


def _source(path, source_type=config.SOURCE_TYPE_FOLDER):
    return models.Source(name="s", path=path, source_type=source_type)


class TestFolderSize:
    def test_somme_recursive(self, tmp_path):
        make_file(str(tmp_path / "a.bin"), 100)
        make_file(str(tmp_path / "sub" / "b.bin"), 200)
        make_file(str(tmp_path / "sub" / "deep" / "c.bin"), 300)
        assert sizing.folder_size(str(tmp_path)) == 600

    def test_dossier_vide(self, tmp_path):
        assert sizing.folder_size(str(tmp_path)) == 0

    def test_dossier_inexistant(self, tmp_path):
        assert sizing.folder_size(str(tmp_path / "absent")) == 0


class TestImageSize:
    def test_ewf_somme_tous_les_segments(self, tmp_path):
        """Piège métier : pointer .E01 doit renvoyer le TOTAL des segments."""
        for ext, size in ((".E01", 100), (".E02", 200), (".E03", 50)):
            make_file(str(tmp_path / f"img{ext}"), size)
        assert sizing.image_size(str(tmp_path / "img.E01")) == 350

    def test_split_dd_somme(self, tmp_path):
        for ext, size in ((".001", 10), (".002", 20)):
            make_file(str(tmp_path / f"disk{ext}"), size)
        assert sizing.image_size(str(tmp_path / "disk.001")) == 30

    def test_ad1_somme(self, tmp_path):
        for ext, size in ((".ad1", 5), (".ad2", 7)):
            make_file(str(tmp_path / f"ad{ext}"), size)
        assert sizing.image_size(str(tmp_path / "ad.ad1")) == 12

    @pytest.mark.parametrize("premier,suivants", [
        (".ex01", (".ex02", ".ex03")),   # EWF v2
        (".L01", (".L02",)),             # LEF (logique)
        (".lx01", (".lx02",)),
        (".s01", (".s02", ".s03")),      # SMART
    ])
    def test_familles_ignorees_avant_le_18_09_2026(self, tmp_path, premier, suivants):
        """Non-régression : ``sizing`` portait une copie incomplète des familles.

        Ces quatre familles sont acceptées à l'import par ``forensic_scan`` mais
        ne matchaient aucun motif local : ``image_size`` retombait sur le fichier
        seul et ne comptait que le 1ᵉ segment, sous-évaluant le volume du cas.
        """
        make_file(str(tmp_path / f"img{premier}"), 100)
        for i, ext in enumerate(suivants, start=2):
            make_file(str(tmp_path / f"img{ext}"), 100 * i)
        attendu = 100 + sum(100 * i for i in range(2, len(suivants) + 2))
        assert sizing.image_size(str(tmp_path / f"img{premier}")) == attendu

    @pytest.mark.parametrize("demande", ["img.E01", "IMG.E01", "Img.e01", "img.e01"])
    def test_casse_du_chemin_demande_sans_effet(self, tmp_path, demande):
        """Non-régression : le radical se comparait à l'identique, l'extension non.

        Windows ne distingue pas la casse : « IMG.E01 » désigne bien le fichier
        « img.E01 » du disque, et ``image_size`` y entrait. Mais le radical
        « IMG » ne correspondait à aucune entrée réelle, ``segments`` sortait
        vide, on retombait sur le fichier seul — 100 octets rendus au lieu de
        350. Un chemin simplement collé dans une autre casse sous-évaluait donc
        le volume du cas (audit du 18/09/2026).
        """
        for ext, size in ((".E01", 100), (".E02", 200), (".E03", 50)):
            make_file(str(tmp_path / f"img{ext}"), size)
        assert sizing.image_size(str(tmp_path / demande)) == 350

    def test_casse_ne_fusionne_pas_deux_images_distinctes(self, tmp_path):
        """La tolérance à la casse ne doit pas rapprocher deux radicaux différents."""
        make_file(str(tmp_path / "scelle_a.E01"), 100)
        make_file(str(tmp_path / "scelle_b.E01"), 900)
        assert sizing.image_size(str(tmp_path / "SCELLE_A.E01")) == 100

    def test_ewf_au_dela_de_e99(self, tmp_path):
        """EWF passe de .E99 aux lettres (.EAA) : même image, même total."""
        for ext, size in ((".E01", 100), (".E99", 200), (".EAA", 300), (".EAB", 400)):
            make_file(str(tmp_path / f"img{ext}"), size)
        assert sizing.image_size(str(tmp_path / "img.E01")) == 1000

    def test_ne_melange_pas_deux_images_du_meme_dossier(self, tmp_path):
        make_file(str(tmp_path / "img1.E01"), 100)
        make_file(str(tmp_path / "img2.E01"), 900)
        assert sizing.image_size(str(tmp_path / "img1.E01")) == 100

    def test_image_mono_fichier(self, tmp_path):
        p = make_file(str(tmp_path / "image.dd"), 42)
        assert sizing.image_size(p) == 42

    def test_image_absente(self, tmp_path):
        assert sizing.image_size(str(tmp_path / "absent.E01")) == 0


class TestSourceSize:
    def test_image_disque(self, tmp_path):
        make_file(str(tmp_path / "i.E01"), 10)
        make_file(str(tmp_path / "i.E02"), 20)
        s = _source(str(tmp_path / "i.E01"), config.SOURCE_TYPE_DISK_IMAGE)
        assert sizing.source_size(s) == 30

    def test_dossier(self, tmp_path):
        make_file(str(tmp_path / "x" / "f.bin"), 64)
        assert sizing.source_size(_source(str(tmp_path / "x"))) == 64

    def test_fichier_unique(self, tmp_path):
        p = make_file(str(tmp_path / "seul.pst"), 128)
        assert sizing.source_size(_source(p)) == 128

    def test_chemin_inexistant(self, tmp_path):
        assert sizing.source_size(_source(str(tmp_path / "nope"))) == 0


class TestProgression:
    def test_on_progress_appele(self, tmp_path, monkeypatch):
        for i in range(5):
            make_file(str(tmp_path / f"f{i}.bin"), 10)
        monkeypatch.setattr(sizing, "PROGRESS_INTERVAL", 0)   # émission à chaque fichier
        vus = []
        sizing.folder_size(str(tmp_path), on_progress=lambda f, b, c: vus.append((f, b)))
        assert [f for f, _b in vus] == [1, 2, 3, 4, 5]
        assert vus[-1][1] == 50

    def test_progression_cadencee(self, tmp_path, monkeypatch):
        """Sans cadence, un dossier de millions de fichiers saturerait la file."""
        for i in range(50):
            make_file(str(tmp_path / f"f{i}.bin"), 1)
        monkeypatch.setattr(sizing, "PROGRESS_INTERVAL", 3600)   # aucune émission
        vus = []
        sizing.folder_size(str(tmp_path), on_progress=lambda *a: vus.append(a))
        assert vus == []

    def test_progression_image(self, tmp_path, monkeypatch):
        for ext in (".E01", ".E02"):
            make_file(str(tmp_path / f"i{ext}"), 10)
        monkeypatch.setattr(sizing, "PROGRESS_INTERVAL", 0)
        vus = []
        sizing.image_size(str(tmp_path / "i.E01"), on_progress=lambda *a: vus.append(a))
        assert len(vus) == 2


class TestAnnulation:
    def test_folder_size_stoppe_et_rend_le_partiel(self, tmp_path):
        for i in range(20):
            make_file(str(tmp_path / f"f{i}.bin"), 100)
        stop = {"v": False}
        appels = {"n": 0}

        def should_stop():
            appels["n"] += 1
            if appels["n"] > 3:
                stop["v"] = True
            return stop["v"]

        total = sizing.folder_size(str(tmp_path), should_stop=should_stop)
        assert 0 <= total < 2000, "le parcours ne s'est pas arrêté"

    def test_image_size_stoppe(self, tmp_path):
        for ext in (".E01", ".E02", ".E03"):
            make_file(str(tmp_path / f"i{ext}"), 100)
        assert sizing.image_size(str(tmp_path / "i.E01"), should_stop=lambda: True) == 0

    def test_sans_annulation_total_complet(self, tmp_path):
        for i in range(10):
            make_file(str(tmp_path / f"f{i}.bin"), 100)
        assert sizing.folder_size(str(tmp_path), should_stop=lambda: False) == 1000


class TestMeasureSources:
    def _items(self, paths):
        return [{"key": p, "path": p, "label": os.path.basename(p),
                 "type": config.SOURCE_TYPE_FOLDER} for p in paths]

    def _drain(self, q):
        msgs = []
        while not q.empty():
            msgs.append(q.get_nowait())
        return msgs

    def test_mesure_complete(self, tmp_path):
        import queue
        d1, d2 = tmp_path / "a", tmp_path / "b"
        make_file(str(d1 / "f.bin"), 100)
        make_file(str(d2 / "f.bin"), 200)
        q = queue.Queue()
        sizing.measure_sources(self._items([str(d1), str(d2)]), q)
        msgs = self._drain(q)
        done = msgs[-1]
        assert done[0] == "done"
        assert done[1] == {str(d1): 100, str(d2): 200}
        assert done[2] == set() and done[3] is False
        assert [m for m in msgs if m[0] == "row"], "aucune ligne terminée postée"
        assert [m for m in msgs if m[0] == "progress"], "aucune progression postée"

    def test_cache_reutilise_sans_scan(self, tmp_path):
        import queue
        d = tmp_path / "a"
        make_file(str(d / "f.bin"), 100)
        q = queue.Queue()
        sizing.measure_sources(self._items([str(d)]), q,
                               cache={sizing.cache_key(str(d)): 999})
        done = self._drain(q)[-1]
        assert done[1] == {str(d): 999} and done[2] == {str(d)}

    def test_annulation_avant_la_premiere_source(self, tmp_path):
        import queue
        d = tmp_path / "a"
        make_file(str(d / "f.bin"), 100)
        q = queue.Queue()
        sizing.measure_sources(self._items([str(d)]), q, should_stop=lambda: True)
        done = self._drain(q)[-1]
        assert done[1] == {} and done[3] is True

    def test_source_interrompue_non_enregistree(self, tmp_path):
        """Contrat : une taille partielle ne doit JAMAIS entrer dans les résultats."""
        import queue
        d1, d2 = tmp_path / "a", tmp_path / "b"
        make_file(str(d1 / "f.bin"), 100)
        make_file(str(d2 / "f.bin"), 200)
        etat = {"stop": False}
        q = queue.Queue()

        items = self._items([str(d1), str(d2)])
        # On demande l'arrêt une fois la 1ʳᵉ source terminée : la 2ᵉ ne doit pas
        # apparaître dans les résultats, même partiellement.
        original = sizing.measure_path

        def measure_path_spy(path, *a, **kw):
            res = original(path, *a, **kw)
            if path == str(d1):
                etat["stop"] = True
            return res

        sizing.measure_path = measure_path_spy
        try:
            sizing.measure_sources(items, q, should_stop=lambda: etat["stop"])
        finally:
            sizing.measure_path = original
        done = self._drain(q)[-1]
        assert str(d2) not in done[1]
        assert done[3] is True

    def test_image_multisegments(self, tmp_path):
        import queue
        for ext, size in ((".E01", 100), (".E02", 200)):
            make_file(str(tmp_path / f"img{ext}"), size)
        p = str(tmp_path / "img.E01")
        q = queue.Queue()
        sizing.measure_sources(
            [{"key": p, "path": p, "label": "img", "type": config.SOURCE_TYPE_DISK_IMAGE}], q)
        assert self._drain(q)[-1][1] == {p: 300}

    def test_cache_key_normalise(self):
        assert sizing.cache_key("D:\\Cas\\Source\\") == "d:\\cas\\source"


class TestOversizedSources:
    def test_seuil_strict(self):
        s1, s2, s3 = _source("a"), _source("b"), _source("c")
        s1.size_bytes, s2.size_bytes, s3.size_bytes = 100, 101, None
        assert sizing.oversized_sources([s1, s2, s3], 100) == [s2]

    def test_taille_none_traitee_comme_zero(self):
        s = _source("a")
        s.size_bytes = None
        assert sizing.oversized_sources([s], 0) == []
