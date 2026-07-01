"""Inventaire **thématique** des options d'indexation d'une source Intella,
pilotables via ``-addSourcesFromJson`` (manuel p.5-6 + Étude 2 du CLAUDE.md).

Un « profil » = jeu nommé de valeurs pour ces options. À la génération, on n'émet
dans le JSON de la source que les options **différentes du défaut** (``défaut`` =
options omises = défauts Intella, cf. Étude 2).

⚠ Les valeurs ``default`` ci-dessous sont les défauts Intella **présumés**
(documentés pour les images/VSC ; raisonnables pour le reste). Elles sont à
**éprouver sur un cas test** (Étude 2). Les options marquées ``confirmed=False``
(nom/effet non confirmés en JSON) portent le libellé « (à éprouver) ».

Chaque option : ``key`` (clé JSON), ``label`` (FR), ``type``
(``bool``/``int``/``str``/``enum``), ``default``, ``choices`` (enum), ``unit``,
``confirmed``, ``applies`` (``all``/``image`` — info UI ; les options ``image``
ne sont émises que sur les sources image disque).
"""

import config

# Clé i18n du titre de chaque groupe thématique (le libellé français ci-dessous
# reste le ``default`` passé à ``i18n.t``). Idem pour chaque option : la clé est
# ``opt.<key>`` (générée plus bas, voir OPTIONS).
GROUP_KEYS = {
    "Messagerie & e-mails": "group.mail",
    "Chats & conversations": "group.chats",
    "Archives & bases de données": "group.archives",
    "Système Windows": "group.windows",
    "Web & navigateurs": "group.browser",
    "Images disque & récupération": "group.images",
    "Volume Shadow Copies (images)": "group.vsc",
    "Texte & analyse": "group.text",
    "Filtres": "group.filters",
    "Cache & avancé": "group.cache",
}

# --- Groupes thématiques (ordre = ordre d'affichage dans l'onglet Profils) --- #
GROUPS = [
    ("Messagerie & e-mails", [
        {"key": "indexMailArchives", "label": "Indexer les archives de messagerie", "type": "bool", "default": True},
        {"key": "emailsGeolocationEnabled", "label": "Géolocalisation des e-mails", "type": "bool", "default": False},
    ]),
    ("Chats & conversations", [
        {"key": "indexChatMessages", "label": "Indexer les messages de chat", "type": "bool", "default": True},
        {"key": "processingMode", "label": "Mode de traitement des chats", "type": "enum",
         "default": "CONVERSATIONS_AND_MESSAGES",
         "choices": ["CONVERSATIONS_AND_MESSAGES", "MESSAGES_ONLY"], "confirmed": False},
        {"key": "splitMode", "label": "Découpage des conversations", "type": "enum",
         "default": "PER_DAY", "choices": ["NONE", "PER_DAY", "PER_MONTH"], "confirmed": False},
        {"key": "numberMessagesPerConversation", "label": "Messages max / conversation", "type": "int", "default": 100},
    ]),
    ("Archives & bases de données", [
        {"key": "indexArchives", "label": "Indexer les archives (zip, rar…)", "type": "bool", "default": True},
        {"key": "indexDatabases", "label": "Indexer les bases de données", "type": "bool", "default": True},
    ]),
    ("Système Windows", [
        {"key": "indexWindowsRegistry", "label": "Indexer le registre Windows", "type": "bool", "default": True},
        {"key": "indexWindowsEventLog", "label": "Indexer les journaux d'événements Windows", "type": "bool", "default": True},
    ]),
    ("Web & navigateurs", [
        {"key": "indexBrowserHistory", "label": "Indexer l'historique de navigation", "type": "bool", "default": True},
    ]),
    ("Images disque & récupération", [
        {"key": "recoverDeleted", "label": "Récupérer les fichiers supprimés", "type": "bool", "default": True},
        {"key": "carveUnallocatedSpace", "label": "Carving de l'espace non alloué", "type": "bool", "default": False, "applies": "image"},
        {"key": "verifyAff4Hashes", "label": "Vérifier les hachages AFF4", "type": "bool", "default": False, "applies": "image"},
    ]),
    ("Volume Shadow Copies (images)", [
        {"key": "indexVolumeShadowCopies", "label": "Indexer les clichés VSS", "type": "bool", "default": False, "applies": "image"},
        {"key": "suppressUnchangedFilesInVsc", "label": "Supprimer les fichiers inchangés (VSS)", "type": "bool", "default": True, "applies": "image"},
        {"key": "preferNewestFilesInVsc", "label": "Préférer les fichiers les plus récents (VSS)", "type": "bool", "default": True, "applies": "image"},
        {"key": "indexChangedLastAccessFilesInVsc", "label": "Tenir compte du dernier accès (VSS)", "type": "bool", "default": True, "applies": "image"},
    ]),
    ("Texte & analyse", [
        {"key": "indexEmbeddedImages", "label": "Indexer les images embarquées", "type": "bool", "default": True},
        {"key": "analyseParagraphs", "label": "Analyser les paragraphes", "type": "bool", "default": True},
        {"key": "indexUnstructured", "label": "Indexer le contenu non structuré", "type": "bool", "default": False, "confirmed": False},
    ]),
    ("Filtres", [
        {"key": "sourceTypeFilter", "label": "Filtre de types MIME (séparés par des virgules)", "type": "str", "default": ""},
        {"key": "sourceTypeFilterMode", "label": "Mode du filtre de types", "type": "enum",
         "default": "exclude", "choices": ["include", "exclude"]},
        {"key": "sourceHashFilters", "label": "Listes de hachages (.md5, séparées par des virgules)", "type": "str", "default": ""},
        {"key": "fileNameFilters", "label": "Filtre de noms de fichiers", "type": "str", "default": "", "confirmed": False},
    ]),
    ("Cache & avancé", [
        {"key": "cacheEvidenceFiles", "label": "Mettre les preuves en cache", "type": "bool", "default": False},
        {"key": "maxBinarySizeToStore", "label": "Taille binaire max stockée", "type": "int", "default": 250, "unit": "Mo"},
        {"key": "custodian", "label": "Dépositaire (custodian)", "type": "str", "default": ""},
        {"key": "enableCrawlerScript", "label": "Activer un script de crawler", "type": "bool", "default": False},
        {"key": "sourceCrawlerScriptType", "label": "Type de script de crawler", "type": "enum",
         "default": "python", "choices": ["python", "javascript"], "confirmed": False},
        {"key": "sourceCrawlerScriptFile", "label": "Fichier de script de crawler", "type": "str", "default": ""},
    ]),
]

# Index plat clé -> option (avec valeurs par défaut des champs facultatifs).
# ``label_key`` : clé i18n (``opt.<key JSON>``) ; ``o["label"]`` (FR) sert de
# valeur ``default`` à ``i18n.t`` dans le formulaire (ui_profiles._build_form).
OPTIONS = {}
for _grp, _opts in GROUPS:
    for _o in _opts:
        _o.setdefault("confirmed", True)
        _o.setdefault("applies", "all")
        _o.setdefault("choices", None)
        _o.setdefault("unit", "")
        _o["label_key"] = f"opt.{_o['key']}"
        OPTIONS[_o["key"]] = _o

# Clés réservées aux images disque (non émises sur une source dossier/fichier).
IMAGE_ONLY_KEYS = {k for k, o in OPTIONS.items() if o["applies"] == "image"}


def default_values() -> dict:
    """Valeurs par défaut de toutes les options (snapshot vierge du formulaire)."""
    return {k: o["default"] for k, o in OPTIONS.items()}


def coerce(key: str, raw):
    """Convertit une valeur saisie/lue vers le type attendu de l'option."""
    o = OPTIONS.get(key)
    if not o:
        return raw
    t = o["type"]
    if t == "bool":
        if isinstance(raw, bool):
            return raw
        return str(raw).strip().lower() in ("1", "true", "vrai", "oui", "yes")
    if t == "int":
        try:
            return int(str(raw).strip())
        except (ValueError, TypeError):
            return o["default"]
    return "" if raw is None else str(raw)


def diff_from_default(values: dict) -> dict:
    """Options à émettre dans le JSON = celles différentes du défaut Intella.

    Respecte le contrat Étude 2 : « défaut = options omises ». Les chaînes vides
    et valeurs égales au défaut sont omises.
    """
    emit = {}
    for k, o in OPTIONS.items():
        if k not in values:
            continue
        v = coerce(k, values[k])
        if o["type"] == "str" and not v.strip():
            continue
        if v != o["default"]:
            emit[k] = v
    # Dépendance : un filtre de types **exige** son mode, sinon IntellaCmd échoue
    # (« Missing source type filter mode »). Le mode est souvent égal au défaut
    # (« exclude ») donc omis par le diff → on le ré-ajoute explicitement.
    if "sourceTypeFilter" in emit and "sourceTypeFilterMode" not in emit:
        mode = coerce("sourceTypeFilterMode",
                      values.get("sourceTypeFilterMode", OPTIONS["sourceTypeFilterMode"]["default"]))
        emit["sourceTypeFilterMode"] = mode or "exclude"
    return emit


def options_for_source(values: dict, source_type: str) -> dict:
    """Options à émettre pour une source : diff du défaut, en retirant les clés
    réservées aux images quand la source n'est pas une image disque."""
    emit = diff_from_default(values)
    if source_type != config.SOURCE_TYPE_DISK_IMAGE:
        emit = {k: v for k, v in emit.items() if k not in IMAGE_ONLY_KEYS}
    return emit
