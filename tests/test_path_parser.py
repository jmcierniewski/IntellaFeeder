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


class TestUncParts:
    @pytest.mark.parametrize("path,expected", [
        ("\\\\NAS\\partage\\Cas\\sous", ("NAS", "partage", "Cas\\sous")),
        ("\\\\192.168.0.174\\partage\\Cas", ("192.168.0.174", "partage", "Cas")),
        ("\\\\NAS\\partage", ("NAS", "partage", "")),
        ("//NAS/partage/Cas", ("NAS", "partage", "Cas")),      # séparateurs unix
    ])
    def test_decoupage(self, path, expected):
        assert path_parser.unc_parts(path) == expected

    @pytest.mark.parametrize("path", [
        "D:\\Cas", "Cas\\sous", "", "\\\\NAS", "\\\\NAS\\", "\\\\?\\C:\\Cas",
    ])
    def test_non_unc(self, path):
        assert path_parser.unc_parts(path) is None


class TestAlignUncHost:
    """Aligner l'hôte d'un sous-cas sur celui du compound (bug du 07/09/2026).

    Un compound ouvert par ``\\\\NAS\\part`` déclarait ses sous-cas par IP :
    lisibles, mais refusés en écriture → ``-exportSourceList`` échouait sur
    ``case.xml.lock``. Windows ouvrant une session SMB par NOM de serveur, la
    seule parade côté outil est de réécrire l'hôte quand le partage est le même.
    """
    COMPOUND = "\\\\NAS_LABO_4\\partage\\CAS CP"

    def test_ip_remplacee_par_le_nom_du_compound(self):
        out = path_parser.align_unc_host("\\\\192.168.0.174\\partage\\CAS (2)",
                                         self.COMPOUND)
        assert out == "\\\\NAS_LABO_4\\partage\\CAS (2)"

    def test_partage_different_laisse_intact(self):
        sub = "\\\\192.168.0.174\\autre_partage\\CAS (2)"
        assert path_parser.align_unc_host(sub, self.COMPOUND) == sub

    def test_meme_hote_casse_ignoree(self):
        sub = "\\\\nas_labo_4\\PARTAGE\\CAS (2)"
        assert path_parser.align_unc_host(sub, self.COMPOUND) == sub

    @pytest.mark.parametrize("sub,ref", [
        ("D:\\Cas\\sous", COMPOUND),                    # sous-cas local
        ("\\\\NAS\\partage\\sous", "D:\\Cas\\CP"),      # compound local
    ])
    def test_hors_unc_laisse_intact(self, sub, ref):
        assert path_parser.align_unc_host(sub, ref) == sub

    def test_racine_de_partage(self):
        assert (path_parser.align_unc_host("\\\\10.0.0.1\\partage", self.COMPOUND)
                == "\\\\NAS_LABO_4\\partage")


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
