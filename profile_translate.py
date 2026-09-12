"""Traduction des réglages d'une source (export ``-exportSourceList``, schéma XML
``indexOptions`` + ``domainBoundaries`` + réglages portés par ``<source>``) vers
les valeurs d'options du catalogue de profils (clés JSON
``-addSourcesFromJson``).

But : « Info Profil » dans l'Inventaire — récupérer les réglages d'une source
(créée au besoin dans la GUI Intella) pour pré-remplir l'onglet Profils, puis
l'enregistrer comme profil. Correspondances issues de l'Étude 2 (CLAUDE.md) et
constatées sur ``Fichiers de cas\\sources.xml``.
"""

import mime_catalog

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
# Réglages portés par ``<source>`` (hors ``<indexOptions>``) que le catalogue
# sait rejouer. ``carveUnallocatedSpace`` est réservé aux images disque —
# `profile_catalog.options_for_source` l'écarte des sources dossier/fichier.
_SOURCE_BOOL_MAP = {
    "carveUnallocatedSpace": "carveUnallocatedSpace",
}

# --- États d'un réglage, pour le visualiseur (3 couleurs) ----------------- #
# Module sans i18n, comme `mime_catalog` : ce sont des identifiants, traduits
# par `ui_widgets`.
STATUS_MAPPED = "mapped"            # bleu : rejoué par le profil
STATUS_UNSUPPORTED = "unsupported"  # noir : présent à la source, non rejouable
STATUS_UNKNOWN = "unknown"          # rouge : nom jamais rencontré, à vérifier

# Motifs de non-rejouabilité (identifiants, traduits côté UI).
REASON_NOT_IN_API = "not_in_api"
REASON_SCRIPT_INCOMPLETE = "script_incomplete"

# Réglages du XML dont on SAIT qu'ils ne sont pas rejouables. Éprouvés le
# 08/09/2026 sur cas jetable : envoyés à `-addSourcesFromJson`, ils sont jetés
# **en silence** (pas d'erreur, pas d'effet) — cf. Étude 3 du CLAUDE.md.
#
# ⚠ Le groupe « script » mérite son propre motif : l'export XML donne bien
# `scriptEnabled` et `scriptType`, mais **jamais le chemin du script**. Rejouer
# l'activation seule armerait un script inexistant — et une clé *reconnue* mal
# renseignée fait ÉCHOUER l'import (manche 5), là où une clé inconnue est
# seulement ignorée. Ne pas les mapper est donc un choix, pas un oubli.
# (Au passage, `scriptType` sort en `PYTHON` quand le catalogue JSON attend
# `python` : un 4e écart de vocabulaire, à ne surtout pas recopier tel quel.)
UNSUPPORTED_REASONS = {
    "isReindexingAllowed": REASON_NOT_IN_API,
    "includeHiddenResources": REASON_NOT_IN_API,
    "scriptEnabled": REASON_SCRIPT_INCOMPLETE,
    "scriptValidated": REASON_SCRIPT_INCOMPLETE,
    "scriptType": REASON_SCRIPT_INCOMPLETE,
    "scriptLogEnabled": REASON_SCRIPT_INCOMPLETE,
}

# Libellé FR des réglages non rejouables (les rejoués empruntent celui du
# catalogue). Un nom absent d'ici et du catalogue est **inconnu** : c'est le
# rouge du visualiseur, et le signal qu'Intella a changé.
XML_LABELS = {
    "isReindexingAllowed": "Réindexation autorisée",
    "includeHiddenResources": "Inclure les ressources cachées",
    "scriptEnabled": "Script de crawler activé",
    "scriptValidated": "Script de crawler validé",
    "scriptType": "Type du script de crawler",
    "scriptLogEnabled": "Journal du script de crawler",
}


def _as_bool(text: str) -> bool:
    return str(text).strip().lower() in ("1", "true", "vrai", "oui", "yes")


def _mapped_xml_keys() -> set:
    """Noms XML que le catalogue sait rejouer, toutes échelles confondues."""
    return (set(_BOOL_MAP) | set(_VERBATIM_MAP) | set(_INT_MAP)
            | set(_SOURCE_BOOL_MAP) | {"crawlerMaxBinarySize"})


def _xml_settings(src: dict) -> dict:
    """Tous les réglages du XML d'une source, les deux échelles réunies.

    ``index_options`` (bloc ``<indexOptions>``) **et** ``source_options``
    (réglages portés par ``<source>``). Ces derniers n'étaient pas lus avant le
    10/09/2026 : le décompte des réglages perdus était donc sous-estimé.
    """
    settings = dict(src.get("index_options") or {})
    settings.update(src.get("source_options") or {})
    return settings


def unsupported_keys(src: dict) -> list:
    """Réglages présents dans l'export XML mais que le catalogue ne connaît pas.

    ⚠ Ces réglages sont **perdus** : « Info Profil » ne recopie que ce que
    `-addSourcesFromJson` sait recevoir, et un profil n'émet que ces options-là.
    Les afficher évite de croire qu'un profil rejoue *tous* les réglages de la
    source d'origine (question posée le 08/09/2026).
    """
    connus = _mapped_xml_keys()
    return sorted(k for k in _xml_settings(src) if k not in connus)


def describe_settings(src: dict) -> list:
    """Tous les réglages du XML, classés pour le visualiseur 3 couleurs.

    Retourne une liste de dicts triée (rejoués d'abord, puis non rejouables,
    puis inconnus ; alphabétique dans chaque groupe) :

    ``xml_key``   nom tel qu'Intella l'écrit dans l'export ;
    ``value``     sa valeur, verbatim ;
    ``status``    ``STATUS_MAPPED`` / ``STATUS_UNSUPPORTED`` / ``STATUS_UNKNOWN`` ;
    ``json_key``  clé ``-addSourcesFromJson`` correspondante (rejoués seuls) ;
    ``label``     libellé FR quand il est connu, sinon "" ;
    ``reason``    motif de non-rejouabilité (identifiant), sinon "".

    C'est cette vue qui remplace le passe-plat abandonné (Étude 3) : à défaut de
    tout rejouer, l'utilisateur voit **exactement** ce qui lui reste à faire à la
    main dans Intella.
    """
    # profile_catalog n'est importé qu'ici : il ne sert qu'aux libellés, et
    # `from_xml_source` doit rester utilisable sans lui.
    import profile_catalog

    mappes = {}
    for table in (_BOOL_MAP, _VERBATIM_MAP, _INT_MAP, _SOURCE_BOOL_MAP):
        mappes.update(table)
    mappes["crawlerMaxBinarySize"] = "maxBinarySizeToStore"

    rangs = {STATUS_MAPPED: 0, STATUS_UNSUPPORTED: 1, STATUS_UNKNOWN: 2}
    lignes = []
    for cle, valeur in _xml_settings(src).items():
        json_key = mappes.get(cle, "")
        if json_key:
            statut = STATUS_MAPPED
            option = profile_catalog.OPTIONS.get(json_key) or {}
            libelle = option.get("label", "")
        elif cle in UNSUPPORTED_REASONS:
            statut = STATUS_UNSUPPORTED
            libelle = XML_LABELS.get(cle, "")
        else:
            statut = STATUS_UNKNOWN
            libelle = XML_LABELS.get(cle, "")
        lignes.append({
            "xml_key": cle,
            "value": valeur,
            "status": statut,
            "json_key": json_key,
            "label": libelle,
            "reason": UNSUPPORTED_REASONS.get(cle, "") if statut != STATUS_MAPPED else "",
        })
    lignes.sort(key=lambda d: (rangs[d["status"]], d["xml_key"].lower()))
    return lignes


def summarize_settings(src: dict) -> dict:
    """Compte des réglages par état — ``{'total': n, STATUS_*: n, ...}``."""
    resume = {"total": 0, STATUS_MAPPED: 0, STATUS_UNSUPPORTED: 0, STATUS_UNKNOWN: 0}
    for ligne in describe_settings(src):
        resume["total"] += 1
        resume[ligne["status"]] += 1
    return resume


def from_xml_source(src: dict) -> dict:
    """``src`` = dict d'une source parsée (voir ``case_export``) contenant
    ``index_options`` (dict) et ``domain_boundaries`` (dict). Retourne les
    valeurs d'options du catalogue présentes dans l'export (les autres restent
    aux défauts côté formulaire)."""
    io = src.get("index_options") or {}
    db = src.get("domain_boundaries") or {}
    so = src.get("source_options") or {}
    values: dict = {}

    for xml_key, json_key in _BOOL_MAP.items():
        if xml_key in io:
            values[json_key] = _as_bool(io[xml_key])
    # Réglages portés par `<source>` : `carveUnallocatedSpace` est au catalogue,
    # il était pourtant perdu faute d'être lu (corrigé le 10/09/2026).
    for xml_key, json_key in _SOURCE_BOOL_MAP.items():
        if xml_key in so:
            values[json_key] = _as_bool(so[xml_key])
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
        # 🐞 Le « ,, » des exports Intella n'est PAS une scorie : le référentiel
        # de Vound porte une entrée à clé vide (`=Untyped`), le type des items
        # dont le format n'a pas été reconnu. L'écarter (ce que faisait le code
        # jusqu'au 09/09/2026) retirait silencieusement un type du filtre.
        values["sourceTypeFilter"] = ",".join(mime_catalog.split_filter(mimes))
    fnf = (db.get("fileNameFilters") or "").strip()
    if fnf:
        values["fileNameFilters"] = fnf

    return values
