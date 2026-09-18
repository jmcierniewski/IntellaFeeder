"""Tableau d'inventaire : les VALEURS suivent la langue, comme les en-têtes.

Les clés des lignes (« Nom », « Type », « Taille »…) sont des identifiants
internes, que le français rend seulement lisibles : ``ui_export`` les traduit à
l'affichage via ``_COLUMN_LABEL_KEYS``. Les valeurs, elles, sont du texte montré
tel quel — elles doivent donc passer par ``i18n``.

🐞 Jusqu'au 18/09/2026 elles étaient en dur : en anglais, une colonne « Type »
traduite surmontait des valeurs « Dossier/Fichier », et la colonne « Size »
affichait « à mesurer ».

Second contrat couvert ici : une source **non mesurée** se reconnaît au booléen
``_size_unknown`` de la ligne, JAMAIS au libellé affiché. Comparer ce libellé à
« à mesurer » (ce que faisait ``ui_export._is_empty_source``) ne reconnaissait
plus rien hors du français — une source non mesurée y passait pour une source
mesurée à 0 octet, c'est-à-dire vide.
"""

import csv

import pytest

import case_export
import config
import i18n


@pytest.fixture
def langue():
    """Charge une langue et restaure l'état de départ — ``i18n`` est global."""
    avant = i18n.current_code() or i18n.BASE_LANGUAGE
    yield i18n.load
    i18n.load(avant)


def _source(nom="s", type_=config.SOURCE_TYPE_FOLDER, octets=0, inconnue=False):
    return {
        "name": nom, "type": type_, "type_raw": "File or Folder",
        "timezone": "UTC", "bytes": octets, "size_unknown": inconnue,
        "parts_count": 0, "primary_path": "D:\\cas\\s", "task_names": [],
    }


class TestLibellesTraduits:
    @pytest.mark.parametrize("code,image,dossier", [
        ("FR", "Image", "Dossier/Fichier"),
        ("US", "Image", "Folder/File"),
    ])
    def test_type_de_source(self, langue, code, image, dossier):
        langue(code)
        assert config.inventory_type_label(config.SOURCE_TYPE_DISK_IMAGE) == image
        assert config.inventory_type_label(config.SOURCE_TYPE_FOLDER) == dossier

    @pytest.mark.parametrize("code,attendu", [("FR", "à mesurer"), ("US", "to measure")])
    def test_taille_non_mesuree(self, langue, code, attendu):
        langue(code)
        assert config.size_unknown_label() == attendu

    def test_type_inconnu_rendu_tel_quel(self, langue):
        """Un type qu'Intella inventerait ne doit pas devenir une clé i18n."""
        langue("US")
        assert config.inventory_type_label("SOMETHING_NEW") == "SOMETHING_NEW"

    def test_repli_francais_sans_langue_chargee(self, langue):
        """Sans traduction, le français en dur reste le socle (cf. i18n)."""
        langue("FR")
        assert config.inventory_type_label(config.SOURCE_TYPE_FOLDER) == \
            config.TYPE_LABELS_INVENTORY[config.SOURCE_TYPE_FOLDER]
        assert config.size_unknown_label() == config.SIZE_UNKNOWN_LABEL


class TestLignesDuTableau:
    @pytest.mark.parametrize("code,dossier,mesurer", [
        ("FR", "Dossier/Fichier", "à mesurer"),
        ("US", "Folder/File", "to measure"),
    ])
    def test_valeurs_dans_la_langue_courante(self, langue, code, dossier, mesurer):
        langue(code)
        rows, _cols = case_export.to_display_rows(
            {"sources": [_source(inconnue=True)]})
        assert rows[0]["Type"] == dossier
        assert rows[0]["Taille"] == mesurer

    def test_image_mesuree_garde_sa_taille_lisible(self, langue):
        langue("US")
        rows, _cols = case_export.to_display_rows(
            {"sources": [_source(type_=config.SOURCE_TYPE_DISK_IMAGE,
                                 octets=2 * config.GB)]})
        assert rows[0]["Type"] == "Image"
        assert rows[0]["Taille"].startswith("2.00")


class TestSourceNonMesuree:
    """``_size_unknown`` : le seul moyen fiable de reconnaître une non-mesurée."""

    @pytest.mark.parametrize("code", ["FR", "US"])
    def test_le_booleen_ne_depend_pas_de_la_langue(self, langue, code):
        langue(code)
        rows, _cols = case_export.to_display_rows({"sources": [
            _source(nom="jamais_mesuree", inconnue=True),
            _source(nom="mesuree_a_zero", octets=0, inconnue=False),
        ]})
        assert rows[0]["_size_unknown"] is True
        assert rows[1]["_size_unknown"] is False
        # Les deux affichent « 0 » octets : sans le booléen, elles seraient
        # indiscernables une fois le libellé traduit.
        assert rows[0]["Octets"] == rows[1]["Octets"] == "0"

    def test_colonne_technique_hors_affichage_et_hors_csv(self):
        assert "_size_unknown" not in case_export.DISPLAY_COLUMNS
        assert "_size_unknown" not in case_export.CSV_COLUMNS
        assert "_size_unknown" not in case_export.DISPLAY_COLUMNS_COMPOUND
        assert "_size_unknown" not in case_export.CSV_COLUMNS_COMPOUND

    def test_csv_ne_laisse_pas_fuir_la_colonne_technique(self, tmp_path):
        rows, _cols = case_export.to_display_rows({"sources": [_source(inconnue=True)]})
        cible = str(tmp_path / "inventaire.csv")
        case_export.export_csv(rows, case_export.CSV_COLUMNS, cible)
        with open(cible, encoding="utf-8-sig", newline="") as fh:
            entetes = next(csv.reader(fh))
        assert entetes == case_export.CSV_COLUMNS
