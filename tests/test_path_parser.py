"""Parsing des chemins collés : nettoyage, dédoublonnage, segments d'image."""

import pytest

import config
import path_parser


class TestNormalizePath:
    @pytest.mark.parametrize("raw,expected", [
        ('  D:\\Cas\\Source  ', "D:\\Cas\\Source"),
        ('"D:\\Cas\\Source"', "D:\\Cas\\Source"),           # consigne projet : guillemets doubles
        ("'D:\\Cas\\Source'", "D:\\Cas\\Source"),           # ... et simples
        ("D:\\Cas\\Source\\", "D:\\Cas\\Source"),           # séparateur final
        ("D:\\Cas\\Source/", "D:\\Cas\\Source"),
        ("\\\\NAS\\partage\\dossier\\", "\\\\NAS\\partage\\dossier"),   # UNC
        ("", ""),
    ])
    def test_nettoyage(self, raw, expected):
        assert path_parser.normalize_path(raw) == expected

    def test_racine_de_lecteur_preservee(self):
        """« C:\\ » ne doit pas être réduit à « C: » (chemin invalide)."""
        assert path_parser.normalize_path("C:\\") == "C:\\"

    def test_clean_field_identique(self):
        assert path_parser.clean_field('  "D:\\x"  ') == path_parser.normalize_path('  "D:\\x"  ')


class TestDeriveName:
    @pytest.mark.parametrize("path,expected", [
        ("D:\\Cas\\Scellé 12", "Scellé 12"),
        ("D:\\Cas\\image.E01", "image.E01"),
        ("D:\\Cas\\dossier\\", "dossier"),
        ("\\\\NAS\\partage\\pièce", "pièce"),
    ])
    def test_dernier_composant(self, path, expected):
        assert path_parser.derive_name(path) == expected


class TestIsNonFirstSegment:
    @pytest.mark.parametrize("path", [
        "D:\\img.E02", "D:\\img.e15", "D:\\img.002", "D:\\img.s02", "D:\\img.ad2", "D:\\img.ad28",
    ])
    def test_segments_non_initiaux(self, path):
        assert path_parser.is_non_first_segment(path) is True

    @pytest.mark.parametrize("path", [
        "D:\\img.E01", "D:\\img.001", "D:\\img.s01", "D:\\img.ad1",
        "D:\\img.dd", "D:\\dossier", "D:\\img.L01",
    ])
    def test_premiers_segments_et_autres(self, path):
        assert path_parser.is_non_first_segment(path) is False


class TestParseLines:
    def test_lignes_vides_ignorees(self):
        srcs = path_parser.parse_lines("D:\\a\n\n   \nD:\\b\n", config.SOURCE_TYPE_FOLDER)
        assert [s.path for s in srcs] == ["D:\\a", "D:\\b"]

    def test_doublons_casse_ignoree(self):
        srcs = path_parser.parse_lines("D:\\Cas\\A\nD:\\cas\\a\n", config.SOURCE_TYPE_FOLDER)
        assert len(srcs) == 1

    def test_type_et_nom_derives(self):
        srcs = path_parser.parse_lines('"D:\\Cas\\image.E01"', config.SOURCE_TYPE_DISK_IMAGE)
        assert (srcs[0].source_type, srcs[0].name) == (config.SOURCE_TYPE_DISK_IMAGE, "image.E01")

    def test_defauts_de_source(self):
        s = path_parser.parse_lines("D:\\a", config.SOURCE_TYPE_FOLDER)[0]
        assert s.size_bytes is None and s.import_selected is True and s.selected_task_ids == set()
