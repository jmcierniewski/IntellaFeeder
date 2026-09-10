"""Réglages portés par ``<source>`` : lecture, rejeu, et vue 3 couleurs.

🐞 **Le défaut corrigé le 10/09/2026.** ``case_export`` ne parsait que
``<indexOptions>`` et ``<domainBoundaries>``. Tout ce qu'Intella écrit
directement sous ``<source>`` — ``includeHiddenResources``,
``carveUnallocatedSpace``, le groupe ``script*`` — n'atteignait donc jamais
``profile_translate``. Deux conséquences, l'une visible et l'autre pas :

* ``carveUnallocatedSpace`` **est au catalogue** : il était rejouable, et il
  était perdu ;
* ``unsupported_keys`` ne regardait que ``index_options``, si bien que le
  nombre de réglages « non repris » annoncé à l'utilisateur était **sous-estimé**
  (1 au lieu de 6 sur une source réelle).

C'est exactement ce que le visualiseur doit rendre visible : le taire laisserait
croire qu'un profil rejoue tous les réglages de la source d'origine.
"""

import xml.etree.ElementTree as ET

import case_export
import profile_translate as pt


def _xml(tmp_path, corps_source: str) -> str:
    """Écrit un export minimal et rend son chemin (aucun cas réel n'est lu)."""
    chemin = tmp_path / "sources.xml"
    chemin.write_text(
        "<sources version='1'><caseId>c</caseId><caseName>n</caseName>"
        "<casePath>p</casePath>"
        "<source>" + corps_source + "</source></sources>",
        encoding="utf-8")
    return str(chemin)


def _source(tmp_path, corps: str) -> dict:
    return case_export.parse_source_list_xml(_xml(tmp_path, corps))["sources"][0]


class TestLectureNiveauSource:
    def test_reglages_hors_index_options_sont_lus(self, tmp_path):
        src = _source(tmp_path,
                      "<name>s</name><type>File or Folder</type>"
                      "<includeHiddenResources>true</includeHiddenResources>"
                      "<scriptEnabled>false</scriptEnabled>")
        assert src["source_options"] == {
            "includeHiddenResources": "true", "scriptEnabled": "false"}

    def test_identite_et_resultats_ecartes(self, tmp_path):
        """``size``/``partsCount``/``tasks``… sont des RÉSULTATS, pas des réglages.

        Les compter ferait passer la taille d'une source pour un réglage perdu.
        """
        src = _source(tmp_path,
                      "<id>42</id><name>s</name><type>Disk Image</type>"
                      "<timeZone>UTC</timeZone><size>10</size><totalSize>20</totalSize>"
                      "<partsCount>2</partsCount><firstPartName>a.E01</firstPartName>"
                      "<lastPartName>a.E02</lastPartName>"
                      "<diskImagePath>X:\\a.E01</diskImagePath><path>X:\\a.E01</path>"
                      "<tasks>[]</tasks>")
        assert src["source_options"] == {}

    def test_balise_inconnue_capturee(self, tmp_path):
        """Liste NOIRE, pas liste blanche : une balise inédite doit APPARAÎTRE.

        Une version future d'Intella ajoutera des réglages. Un filtre par liste
        blanche les ferait disparaître en silence — or c'est précisément ce que
        le visualiseur est chargé de montrer (en rouge).
        """
        src = _source(tmp_path, "<name>s</name><futureIntellaOption>7</futureIntellaOption>")
        assert src["source_options"]["futureIntellaOption"] == "7"

    def test_blocs_imbriques_non_aplatis(self, tmp_path):
        """``<indexOptions>`` et consorts sont lus à part : pas de doublon ici."""
        src = _source(tmp_path,
                      "<name>s</name>"
                      "<indexOptions><indexArchives>true</indexArchives></indexOptions>"
                      "<domainBoundaries><includeMode>Exclude selected entries"
                      "</includeMode></domainBoundaries>")
        assert src["source_options"] == {}
        assert src["index_options"] == {"indexArchives": "true"}


class TestRejeu:
    def test_carve_unallocated_space_rejoue(self):
        """🐞 Réglage AU CATALOGUE, pourtant perdu faute d'être lu."""
        vals = pt.from_xml_source({"source_options": {"carveUnallocatedSpace": "true"}})
        assert vals["carveUnallocatedSpace"] is True

    def test_groupe_script_non_rejoue(self):
        """Choix délibéré : l'export ne donne PAS le chemin du script.

        Rejouer ``scriptEnabled`` seul armerait un script absent — et une clé
        *reconnue* mal renseignée fait ÉCHOUER l'import, là où une clé inconnue
        est seulement ignorée (manche 5, 08/09/2026). Au passage, l'export écrit
        ``PYTHON`` quand le catalogue JSON attend ``python``.
        """
        vals = pt.from_xml_source({"source_options": {
            "scriptEnabled": "true", "scriptType": "PYTHON"}})
        assert vals == {}


class TestDecompteDesPertes:
    def test_unsupported_compte_les_deux_echelles(self):
        """Le décompte annoncé était sous-estimé : 1 clé au lieu de 6."""
        src = {"index_options": {"indexArchives": "true", "isReindexingAllowed": "true"},
               "source_options": {"includeHiddenResources": "true",
                                  "scriptEnabled": "false"}}
        assert pt.unsupported_keys(src) == [
            "includeHiddenResources", "isReindexingAllowed", "scriptEnabled"]


class TestVisualiseur:
    def test_trois_etats(self):
        lignes = {l["xml_key"]: l for l in pt.describe_settings({
            "index_options": {"indexArchives": "true", "isReindexingAllowed": "false"},
            "source_options": {"futureIntellaOption": "7"}})}
        assert lignes["indexArchives"]["status"] == pt.STATUS_MAPPED
        assert lignes["isReindexingAllowed"]["status"] == pt.STATUS_UNSUPPORTED
        assert lignes["futureIntellaOption"]["status"] == pt.STATUS_UNKNOWN

    def test_rejoue_porte_sa_cle_json_et_son_libelle(self):
        ligne = pt.describe_settings({"index_options": {"analyzeParagraphs": "true"}})[0]
        assert ligne["json_key"] == "analyseParagraphs"
        assert ligne["label"]        # libellé emprunté au catalogue
        assert ligne["value"] == "true"

    def test_motif_de_non_rejeu_expose(self):
        lignes = {l["xml_key"]: l for l in pt.describe_settings({
            "source_options": {"scriptEnabled": "true", "includeHiddenResources": "true"}})}
        assert lignes["scriptEnabled"]["reason"] == pt.REASON_SCRIPT_INCOMPLETE
        assert lignes["includeHiddenResources"]["reason"] == pt.REASON_NOT_IN_API

    def test_ordre_rejoues_puis_perdus_puis_inconnus(self):
        """L'utilisateur lit d'abord ce qui est acquis, ensuite ce qui reste à faire."""
        etats = [l["status"] for l in pt.describe_settings({
            "index_options": {"zzUnknown": "1", "isReindexingAllowed": "true",
                              "indexArchives": "true"}})]
        assert etats == [pt.STATUS_MAPPED, pt.STATUS_UNSUPPORTED, pt.STATUS_UNKNOWN]

    def test_resume(self):
        r = pt.summarize_settings({
            "index_options": {"indexArchives": "true", "isReindexingAllowed": "true"},
            "source_options": {"futureIntellaOption": "7"}})
        assert r == {"total": 3, pt.STATUS_MAPPED: 1,
                     pt.STATUS_UNSUPPORTED: 1, pt.STATUS_UNKNOWN: 1}

    def test_source_sans_reglage(self):
        assert pt.describe_settings({}) == []
        assert pt.summarize_settings({})["total"] == 0
