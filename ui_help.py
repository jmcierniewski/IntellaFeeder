"""Onglet Aide : mode d'emploi destiné à l'utilisateur final.

Texte volontairement accessible (pas de détails techniques internes, pas de
changelog). Décrit le déroulé, les astuces de l'interface et le comportement
quand un cas devient trop volumineux.
"""

import re
import tkinter as tk
from tkinter import ttk

import config
import i18n

# Contenu structuré : (style, texte). Styles : "h1", "h2", "p", "b" (puce).
# Repli si le dossier ``lang\`` est absent/corrompu : le français reste toujours
# disponible (identique au contenu de ``lang\FR.lang``). En fonctionnement
# normal, le contenu réellement affiché vient de ``i18n.help_content()``.
_DEFAULT_CONTENT = [
    ("h1", f"{config.APP_NAME} — Aide"),
    ("p", "Cet outil prépare l'import automatique de sources dans un cas Intella "
          "déjà créé, sans repasser par l'assistant web. Vous collez des listes "
          "de chemins, choisissez les tâches à appliquer, et l'outil génère les "
          "fichiers et un script « .bat » prêt à lancer."),

    ("h1", "Déroulé recommandé"),
    ("b", "1. Onglet « Inventaire du cas » : lisez d'abord les sources déjà "
          "présentes dans le cas. Cela sert à connaître le volume déjà occupé et "
          "à repérer les sources déjà indexées (pour ne pas les ajouter deux fois). "
          "Le bouton « Exporter le XML » enregistre une copie de la liste lue."),
    ("b", "2. Onglet « Import » : collez les chemins des nouvelles sources "
          "(1 chemin par ligne) — images forensiques à gauche, dossiers/fichiers "
          "à droite."),
    ("b", "3. Cliquez « Récapituler » : le tableau liste les sources. Les sources "
          "déjà présentes dans le cas (d'après l'inventaire) sont surlignées."),
    ("b", "4. Cliquez « Calculer la taille » pour connaître le volume des sources."),
    ("b", "5. Cochez, pour chaque source, les tâches annexes à exécuter "
          "(colonnes T1, T2…)."),
    ("b", "6. Cliquez « Générer » : l'outil écrit les fichiers de sortie et le(s) "
          "script(s) « .bat ». Lancez le « .bat » pour réaliser l'import dans Intella."),

    ("h1", "Astuces de l'interface"),
    ("b", "Nom réel d'une tâche : passez la souris sur l'en-tête d'une colonne "
          "T1, T2… (ou sur ses boutons ✓ / ✗) pour afficher le nom complet de la tâche."),
    ("b", "Tri : cliquez sur un en-tête de colonne pour trier (une flèche ▲ / ▼ "
          "indique le sens). Un nouveau clic inverse le tri."),
    ("b", "Défilement horizontal : la barre du bas permet de voir toutes les "
          "colonnes de tâches quand elles sont nombreuses."),
    ("b", "Renommer une source : double-cliquez sur son nom dans le tableau."),
    ("b", "Cocher / décocher vite : « Tout cocher / décocher », ou les boutons "
          "« T1 ✓ / T1 ✗ » pour (dé)cocher toute une colonne d'un coup."),
    ("b", "Guillemets : vous pouvez coller des chemins entre guillemets, ils sont "
          "nettoyés automatiquement."),
    ("b", "Images en plusieurs morceaux (.E01/.E02… ou .ad1/.ad2…) : indiquez "
          "seulement le PREMIER segment ; les autres sont pris en compte tout seuls."),

    ("h1", "Profils de paramètres d'analyse"),
    ("p", "Un « profil » regroupe des réglages d'indexation (messagerie, archives, "
          "récupération de fichiers supprimés, filtres…) que vous appliquez à une "
          "source à l'import. Ils se créent dans l'onglet « Profils » et sont "
          "partagés entre vos cas."),
    ("b", "Dans l'onglet « Profils » : choisissez un profil dans la liste pour voir "
          "ses options, ou « Nouveau » pour partir des réglages par défaut. Cochez "
          "les options voulues, donnez un nom, puis « Enregistrer »."),
    ("b", "Le profil « défaut » applique les réglages standard d'Intella : il ne "
          "force aucune option et n'est pas modifiable."),
    ("b", "Astuce « Info Profil » : réglez une source d'exemple dans Intella, puis "
          "dans l'onglet « Inventaire du cas », lisez les sources, sélectionnez "
          "cette source et cliquez « Info Profil → ». Ses réglages (y compris le "
          "filtre de types) remplissent automatiquement l'onglet Profils : il ne "
          "reste qu'à nommer et enregistrer le profil."),
    ("b", "Chaque profil est enregistré dans un fichier du dossier « profils » "
          "(à côté du programme) ; vous pouvez les sauvegarder ou les partager. "
          "Le champ « Commentaires » (en haut) permet d'y noter à quoi sert le profil."),
    ("b", "Filtre de nom de fichiers : vous pouvez utiliser les jokers « ? » "
          "(un caractère) et « * » (plusieurs caractères), ex. rapport_*.pdf."),
    ("b", "Filtre de types MIME : c'est une longue liste ; la zone s'agrandit "
          "quand vous cliquez dedans pour copier/coller plus facilement."),
    ("b", "Dans le récapitulatif de l'onglet Import, la colonne « Profil » permet "
          "de choisir le profil de chaque source. Le menu « Profil par défaut » "
          "applique le profil choisi à toutes les lignes d'un coup."),

    ("h1", "Types MIME pour le filtre de types"),
    ("p", "Le champ « Filtre de types MIME » attend une liste séparée par des "
          "virgules, à combiner avec le mode « inclure » ou « exclure ». Cette "
          "liste mélange DEUX niveaux qui cohabitent :"),
    ("b", "Les CATÉGORIES Intella (« category/… ») : de vrais regroupements "
          "thématiques d'Intella. Cocher une catégorie sélectionne d'un coup tous "
          "les formats qu'elle contient."),
    ("b", "Les TYPES INDIVIDUELS (« application/x-pdf », « application/rtf »…) : un "
          "format précis, coché à l'unité, indépendamment de sa catégorie."),
    ("p", "Un type individuel n'est donc PAS « contenu » dans un « category/… » de "
          "la liste : les deux se choisissent séparément. Exemple : application/x-pdf "
          "relève thématiquement des Documents, mais se coche seul (Intella "
          "n'imbrique pas). La liste exacte dépend de votre cas — le plus fiable est "
          "d'utiliser « Info Profil » sur une source réglée dans Intella."),

    ("h2", "Catégories Intella (les vraies catégories)"),
    ("pcsv", "category/accounts, category/browser_cookies, category/browser_downloads, "
          "category/chat, category/contacts, category/containers, "
          "category/crypto_currency, category/formulas, category/graphics, "
          "category/hangul_document, category/launched_programs, category/media, "
          "category/other_communications, category/other_documents, "
          "category/other_media, category/others, category/presentations, "
          "category/recently_accessed_files, category/scheduling, category/system, "
          "category/user_activity, category/user_sessions, category/video, "
          "category/voice, category/word_processing"),

    ("h2", "Types individuels (formats précis)"),
    ("p", "Ce ne sont PAS des catégories Intella. Le regroupement par thème "
          "ci-dessous est le nôtre, uniquement pour faciliter la lecture."),
    ("bcsv", "Traitement de texte & bureautique : application/rtf, text/rtf, "
          "application/x-pdf, application/msonenote, application/vnd.fdf, "
          "application/vnd.framemaker, application/x-framemaker, "
          "application/vnd.ms-publisher, application/vnd.ms-xpsdocument, "
          "application/vnd.oasis.opendocument.text (et -master, -template, -web), "
          "application/vnd.stardivision.writer (et -global), "
          "application/vnd.stardivision.math, application/vnd.stardivision.draw, "
          "application/vnd.sun.xml.writer (et .template), application/vnd.wordperfect, "
          "application/wps-office.wps/.wpt/.dpt/.ett, application/x-mspowerpoint, "
          "text/vnd.wap.wml"),
    ("bcsv", "Images, vidéo & média : image/iff, image/x-iff, application/iff, "
          "application/x-iff, application/ogg, application/riff, "
          "application/x-iso-base-media, application/x-shockwave-flash, "
          "video/x-ms-asf, video/x-ms-wm"),
    ("bcsv", "Archives & conteneurs : application/binhex, application/unix-v7-tar, "
          "application/x-java-webarchive, application/x-rar-compressed-v5, "
          "application/x-sitx"),
    ("bcsv", "Artefacts Windows & forensic (Intella) : application/vnd.ms-registry, "
          "application/vnd.ms-registry-key, "
          "application/vnd.ms-windows-xml-event-log-entry, "
          "application/x-intella-windows-registry-artifacts, "
          "application/x-intella-windows-shellbag, "
          "application/x-intella-windows-10-timeline-entry, "
          "application/x-intella-windows-push-notification-entry, "
          "application/x-intella-operating-system-information, "
          "application/x-intella-startup-program, "
          "application/x-intella-installed-application, "
          "application/x-intella-time-zone-information, "
          "application/x-intella-usb-storage-device, "
          "application/x-intella-boot-sector-file, "
          "application/x-intella-net-connection, "
          "application/x-intella-device-acquisition, "
          "application/x-intella-aws-s3-bucket, "
          "application/x-intella-imap-connection, "
          "application/x-intella-sharepoint-post"),
    ("bcsv", "Réseau & e-mail : application/pcap, application/vnd.tcpdump.pcap, "
          "message/rfc822-headers, application/applefile, multipart/appledouble"),

    ("h1", "Images en plusieurs morceaux : intégrité"),
    ("p", "Une anomalie connue de l'éditeur (Vound) peut faire échouer la "
          "vérification d'intégrité des images forensiques découpées en plusieurs "
          "fichiers. En attendant un correctif, l'onglet Import propose une case "
          "« Ne pas vérifier l'intégrité des sources »."),
    ("b", "Quand elle est cochée, l'option « -validateDiskImage false » est ajoutée "
          "automatiquement au champ « Arguments suppl. » : l'import n'effectue plus "
          "la vérification d'intégrité. Le réglage est mémorisé pour chaque cas."),

    ("h1", "Éviter la double indexation"),
    ("p", "Après avoir lu l'inventaire d'un cas, l'onglet Import compare les "
          "chemins que vous collez avec ceux déjà indexés. Les sources déjà "
          "présentes sont retirées automatiquement du récapitulatif (au "
          "« Récapituler » comme à l'import d'une liste)."),

    ("h1", "Quand le cas devient trop grand"),
    ("p", f"Un cas Intella est limité (ici {config.DEFAULT_SIZE_LIMIT_GB} Go par "
          "sécurité, sur 1 To autorisé). L'outil additionne le volume déjà présent "
          "dans le cas et celui des nouvelles sources :"),
    ("b", "Si le total tient sous la limite : un seul import, dans le cas existant."),
    ("b", "Si le total dépasse la limite : l'outil PRÉVIENT, décoche "
          "automatiquement les dernières sources pour ne garder que ce qui tient, "
          "et SUSPEND la génération (rien n'est écrit). Aucun sous-cas n'est créé "
          "automatiquement."),
    ("b", "Marche à suivre : vérifiez/ajustez les cases « Imp. » puis relancez "
          "« Générer » pour importer ce que vous gardez. Pour le reste : créez le "
          "sous-cas manuellement dans Intella, ciblez-le comme cas, recochez et "
          "réimportez les sources restantes."),
    ("b", "La colonne « Imp. » (case à cocher) choisit les sources à mesurer et à "
          "importer ; la croix « ✕ » retire une ligne du récapitulatif. Les boutons "
          "« Exporter / Importer une liste » sauvegardent l'état du récapitulatif."),
    ("b", "Une source seule plus grande que la limite ne peut pas être importée "
          "telle quelle : elle est signalée."),
    ("p", "Remarque : le volume des sources de type « dossier » n'est pas toujours "
          "connu via l'inventaire ; dans ce cas le total affiché est marqué "
          "« partiel » et la décision peut être optimiste. Vérifiez ces dossiers "
          "si vous êtes proche de la limite."),
]


class HelpTab(ttk.Frame):
    def __init__(self, parent, app):
        super().__init__(parent)
        self.app = app

        holder = ttk.Frame(self)
        holder.pack(fill="both", expand=True, padx=8, pady=8)
        text = tk.Text(holder, wrap="word", state="disabled", padx=10, pady=10,
                       relief="flat", cursor="arrow")
        vsb = ttk.Scrollbar(holder, orient="vertical", command=text.yview)
        text.configure(yscrollcommand=vsb.set)
        text.pack(side="left", fill="both", expand=True)
        vsb.pack(side="right", fill="y")
        self.text = text

        text.tag_configure("h1", font=("Segoe UI", 13, "bold"),
                            foreground="#1e40af", spacing1=12, spacing3=6)
        text.tag_configure("h2", font=("Segoe UI", 11, "bold"), spacing1=8, spacing3=4)
        text.tag_configure("p", font=("Segoe UI", 10), spacing3=6, lmargin1=4, lmargin2=4)
        text.tag_configure("b", font=("Segoe UI", 10), spacing3=4,
                            lmargin1=16, lmargin2=28)
        # Séparateur bien visible entre types MIME (styles « pcsv »/« bcsv ») :
        # une puce « • » bleue en gras remplace la virgule (peu lisible).
        text.tag_configure("csvcomma", font=("Segoe UI", 11, "bold"), foreground="#2563eb")
        text.tag_raise("csvcomma")

        self._render()

    def _insert_csv(self, body, base):
        """Insère ``body`` (tag ``base``) en remplaçant chaque virgule séparatrice
        par une puce « • » bleue en gras, bien plus lisible qu'une virgule."""
        parts = [p for p in re.split(r",\s*", body) if p]
        for i, part in enumerate(parts):
            if i:
                self.text.insert("end", "  •  ", (base, "csvcomma"))
            self.text.insert("end", part, base)

    def _render(self):
        content = i18n.help_content() or _DEFAULT_CONTENT
        self.text.configure(state="normal")
        self.text.delete("1.0", "end")
        for style, body in content:
            if style == "b":
                self.text.insert("end", "•  " + body + "\n", "b")
            elif style == "bcsv":                 # puce + virgules en gras
                self.text.insert("end", "•  ", "b")
                self._insert_csv(body, "b")
                self.text.insert("end", "\n", "b")
            elif style == "pcsv":                 # paragraphe + virgules en gras
                self._insert_csv(body, "p")
                self.text.insert("end", "\n", "p")
            else:
                self.text.insert("end", body + "\n", style)
        self.text.configure(state="disabled")
