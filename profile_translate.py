"""Traduction des réglages d'une source (export ``-exportSourceList``, schéma XML
``indexOptions`` + ``domainBoundaries``) vers les valeurs d'options du catalogue
de profils (clés JSON ``-addSourcesFromJson``).

But : « Info Profil » dans l'Inventaire — récupérer les réglages d'une source
(créée au besoin dans la GUI Intella) pour pré-remplir l'onglet Profils, puis
l'enregistrer comme profil. Correspondances issues de l'Étude 2 (CLAUDE.md) et
constatées sur ``Fichiers de cas\\sources.xml``.
"""

# XML indexOptions -> clé JSON catalogue. (bool sauf mention.)
_BOOL_MAP = {
    "indexMailContainers": "indexMailArchives",
    "indexChats": "indexChatMessages",
    "indexArchives": "indexArchives",
    "indexEmbedded": "indexEmbeddedImages",
    "indexDatabases": "indexDatabases",
    "indexWindowsRegistry": "indexWindowsRegistry",
    "indexWindowsEventLog": "indexWindowsEventLog",
    "indexBrowserHistory": "indexBrowserHistory",
    "recoverDeleted": "recoverDeleted",
    "extractTextFragments": "indexUnstructured",   # à confirmer
    "cacheOriginalEvidence": "cacheEvidenceFiles",
    "analyzeParagraphs": "analyseParagraphs",       # orthographe GB côté JSON
    "determineEmailGeoIp": "emailsGeolocationEnabled",
}
# XML -> clé JSON, valeur texte recopiée telle quelle (enum/str).
_VERBATIM_MAP = {
    "chatsProcessingMode": "processingMode",
    "chatSplitMode": "splitMode",
}
# XML -> clé JSON, valeur entière.
_INT_MAP = {
    "chatMaxNumberOfMessages": "numberMessagesPerConversation",
}


def _as_bool(text: str) -> bool:
    return str(text).strip().lower() in ("1", "true", "vrai", "oui", "yes")


def from_xml_source(src: dict) -> dict:
    """``src`` = dict d'une source parsée (voir ``case_export``) contenant
    ``index_options`` (dict) et ``domain_boundaries`` (dict). Retourne les
    valeurs d'options du catalogue présentes dans l'export (les autres restent
    aux défauts côté formulaire)."""
    io = src.get("index_options") or {}
    db = src.get("domain_boundaries") or {}
    values: dict = {}

    for xml_key, json_key in _BOOL_MAP.items():
        if xml_key in io:
            values[json_key] = _as_bool(io[xml_key])
    for xml_key, json_key in _VERBATIM_MAP.items():
        if io.get(xml_key, "").strip():
            values[json_key] = io[xml_key].strip()
    for xml_key, json_key in _INT_MAP.items():
        if xml_key in io:
            try:
                values[json_key] = int(str(io[xml_key]).strip())
            except (ValueError, TypeError):
                pass

    # crawlerMaxBinarySize (octets) -> maxBinarySizeToStore (Mo).
    raw = io.get("crawlerMaxBinarySize")
    if raw not in (None, ""):
        try:
            values["maxBinarySizeToStore"] = int(round(int(str(raw).strip()) / (1024 ** 2)))
        except (ValueError, TypeError):
            pass

    # domainBoundaries : mode + filtre MIME + filtre de nom de fichier.
    mode = (db.get("includeMode") or "").strip().lower()
    if mode:
        values["sourceTypeFilterMode"] = "include" if "include" in mode else "exclude"
    mimes = (db.get("mimeTypes") or "").strip()
    if mimes:
        # Nettoie les entrées vides (« ,, » constaté dans les exports Intella).
        parts = [p.strip() for p in mimes.split(",") if p.strip()]
        values["sourceTypeFilter"] = ",".join(parts)
    fnf = (db.get("fileNameFilters") or "").strip()
    if fnf:
        values["fileNameFilters"] = fnf

    return values
