"""Traduction XML (export -exportSourceList) → options de profil (« Info Profil »).

Pièges couverts : renommages de clés, orthographe GB (``analyseParagraphs``) et
surtout la **conversion d'unité** ``crawlerMaxBinarySize`` (octets) →
``maxBinarySizeToStore`` (Mo).
"""

import profile_translate as pt


def _src(index_options=None, domain_boundaries=None):
    return {"index_options": index_options or {}, "domain_boundaries": domain_boundaries or {}}


class TestRenommages:
    def test_cles_booleennes(self):
        vals = pt.from_xml_source(_src({
            "indexMailContainers": "true",
            "indexChats": "false",
            "indexEmbedded": "true",
            "cacheOriginalEvidence": "false",
            "determineEmailGeoIp": "true",
        }))
        assert vals["indexMailArchives"] is True
        assert vals["indexChatMessages"] is False
        assert vals["indexEmbeddedImages"] is True
        assert vals["cacheEvidenceFiles"] is False
        assert vals["emailsGeolocationEnabled"] is True

    def test_orthographe_gb(self):
        """XML « analyzeParagraphs » (US) → JSON « analyseParagraphs » (GB)."""
        assert pt.from_xml_source(_src({"analyzeParagraphs": "true"}))["analyseParagraphs"] is True

    def test_enums_recopies_verbatim(self):
        vals = pt.from_xml_source(_src({
            "chatsProcessingMode": " MESSAGES_ONLY ", "chatSplitMode": "PER_MONTH"}))
        assert vals["processingMode"] == "MESSAGES_ONLY"
        assert vals["splitMode"] == "PER_MONTH"

    def test_entier(self):
        vals = pt.from_xml_source(_src({"chatMaxNumberOfMessages": "250"}))
        assert vals["numberMessagesPerConversation"] == 250

    def test_cles_absentes_non_inventees(self):
        assert pt.from_xml_source(_src({})) == {}


class TestConversionUnite:
    def test_octets_vers_mo(self):
        vals = pt.from_xml_source(_src({"crawlerMaxBinarySize": str(50 * 1024 ** 2)}))
        assert vals["maxBinarySizeToStore"] == 50

    def test_arrondi(self):
        vals = pt.from_xml_source(_src({"crawlerMaxBinarySize": str(int(1.6 * 1024 ** 2))}))
        assert vals["maxBinarySizeToStore"] == 2

    def test_valeur_invalide_ignoree(self):
        assert "maxBinarySizeToStore" not in pt.from_xml_source(_src({"crawlerMaxBinarySize": "abc"}))

    def test_valeur_vide_ignoree(self):
        assert "maxBinarySizeToStore" not in pt.from_xml_source(_src({"crawlerMaxBinarySize": ""}))


class TestDomainBoundaries:
    def test_mode_include(self):
        vals = pt.from_xml_source(_src(domain_boundaries={"includeMode": "INCLUDE"}))
        assert vals["sourceTypeFilterMode"] == "include"

    def test_mode_exclude_par_defaut(self):
        vals = pt.from_xml_source(_src(domain_boundaries={"includeMode": "EXCLUDE"}))
        assert vals["sourceTypeFilterMode"] == "exclude"

    def test_mime_entree_vide_conservee_une_fois(self):
        """🐞 Le « ,, » d'un export Intella EST un type : « Untyped ».

        Corrigé le 09/09/2026 : le référentiel de Vound porte une entrée à clé
        vide (``=Untyped``), celle des items dont le format n'a pas été reconnu.
        L'ancien code la retirait, ce qui **modifiait le filtre en silence** —
        une source réelle du 08/09 en portait une.
        Les segments vides multiples se réduisent à un seul (dédoublonnage).
        """
        vals = pt.from_xml_source(_src(domain_boundaries={
            "mimeTypes": "application/pdf,, ,image/jpeg,"}))
        assert vals["sourceTypeFilter"] == "application/pdf,,image/jpeg"

    def test_filtre_nom_de_fichier(self):
        vals = pt.from_xml_source(_src(domain_boundaries={"fileNameFilters": "*.tmp"}))
        assert vals["fileNameFilters"] == "*.tmp"

    def test_champs_vides_ignores(self):
        vals = pt.from_xml_source(_src(domain_boundaries={
            "includeMode": "", "mimeTypes": "  ", "fileNameFilters": ""}))
        assert vals == {}


class TestSourceIncomplete:
    def test_dict_vide(self):
        assert pt.from_xml_source({}) == {}

    def test_valeurs_none(self):
        assert pt.from_xml_source({"index_options": None, "domain_boundaries": None}) == {}
