"""Fabrique un squelette de test à partir d'un vrai cas Intella (compound ou non).

Copie uniquement ce dont IntellaFeeder a besoin pour fonctionner — ``case.xml``
du cas et de chacun de ses sous-cas, ``prefs\\case.prefs``, ``prefs\\tasks2.json``,
les exports ``-exportSourceList``, les ``IF_<cas>.info``, les ``.ini`` — en
reproduisant l'arborescence. Le résultat sert de banc d'essai : on développe et
on rejoue les scénarios compound sans le serveur ni le cas d'origine.

    python squelette_cas.py <dossier du cas> <dossier de sortie> [options]

**Anonymisé par défaut.** Un cas réel porte des noms de cas, d'utilisateurs et
des chemins qui n'ont rien à faire dans un jeu d'essai : le mode par défaut
remplace ces valeurs par ``CAS_1``, ``user1``, ``D:\\Preuves\\…`` en conservant ce
qui compte pour les tests — structure XML, tailles, fuseaux, options
d'indexation, nombre de segments, forme des chemins (UNC ou lettre de lecteur).
Le squelette est alors lisible et diffusable. ``--brut`` copie à l'identique :
utile pour reproduire un défaut qui ne se manifeste que sur les vraies valeurs,
mais le dossier produit contient alors des données réelles.

Les **logs** ne sont pas anonymisables de façon fiable (texte libre) : par
défaut ils sont seulement inventoriés (nom, taille, nombre de lignes). Les
copier demande ``--logs brut``, refusé hors ``--brut``.

Autonome : bibliothèque standard uniquement, aucun import d'IntellaFeeder, aucun
IntellaCmd. À lancer depuis n'importe où.
"""

from __future__ import annotations

import argparse
import hashlib
import io
import json
import os
import re
import shutil
import sys
import xml.etree.ElementTree as ET

CASE_XML = "case.xml"
PREFS_DIR = "prefs"
CASE_PREFS = "case.prefs"
TASKS2_JSON = "tasks2.json"
LOGS_DIR = "logs"
MANIFESTE = "MANIFESTE.md"

# Profondeur maximale de descente dans les sous-cas : un compound référençant
# (par erreur ou par boucle) un cas déjà vu doit s'arrêter, pas tourner.
MAX_PROFONDEUR = 5

# Emplacement fictif des cas dans un squelette anonymise.
DOSSIER_FICTIF = "D:" + chr(92) + "SquelettesTest"
SEPARATEURS = chr(92) + "/"


# --------------------------------------------------------------------------- #
# Anonymisation                                                                #
# --------------------------------------------------------------------------- #
class Anonymiseur:
    """Table de substitution stable : une même valeur donne toujours le même alias.

    La stabilité compte plus que le secret : c'est elle qui garde le squelette
    cohérent (le sous-cas nommé dans le ``case.xml`` parent est celui qu'on
    retrouve dans son propre dossier). Inactif en mode ``--brut``.
    """

    def __init__(self, actif: bool = True):
        self.actif = actif
        self._tables: dict[str, dict[str, str]] = {}

    def _alias(self, famille: str, valeur: str, gabarit: str) -> str:
        if not self.actif or not valeur:
            return valeur
        table = self._tables.setdefault(famille, {})
        if valeur not in table:
            table[valeur] = gabarit.format(n=len(table) + 1)
        return table[valeur]

    def cas(self, nom: str) -> str:
        return self._alias("cas", nom, "CAS_{n}")

    def user(self, nom: str) -> str:
        return self._alias("user", nom, "user{n}")

    def source(self, nom: str) -> str:
        return self._alias("source", nom, "SOURCE_{n}")

    def tache(self, nom: str) -> str:
        return self._alias("tache", nom, "Tache {n}")

    def texte_libre(self, valeur: str) -> str:
        """Description, commentaire : remplacé par un texte neutre de même esprit."""
        if not self.actif or not valeur:
            return valeur
        return "texte de test ({} caracteres a l'origine)".format(len(valeur))

    def identifiant(self, guid: str) -> str:
        """GUID/UUID : régénéré, **même forme** (longueur et tirets conservés).

        Les identifiants circulent entre fichiers (id de cas, id de tâche) : les
        dériver du hash de l'original garde les correspondances intactes.
        """
        if not self.actif or not guid:
            return guid
        chiffres = hashlib.sha256(guid.encode("utf-8")).hexdigest()
        sortie, i = [], 0
        for car in guid:
            if car.isalnum():
                sortie.append(chiffres[i % len(chiffres)])
                i += 1
            else:
                sortie.append(car)
        return "".join(sortie)

    def nom_fichier(self, nom: str) -> str:
        """Nom de fichier NU (``firstPartName``) : alias + extension conservée.

        Distinct de ``chemin_preuve``, qui fabriquerait un chemin complet là où
        Intella n'attend qu'un nom — le squelette cesserait d'être représentatif.
        """
        if not self.actif or not nom:
            return nom
        _base, ext = os.path.splitext(nom)
        return self._alias("fichier", nom, "fichier_{n}") + ext

    def chemin_cas(self, chemin: str) -> str:
        """Chemin d'un dossier de cas → emplacement fictif portant son alias.

        L'alias vient du ``<name>`` du ``case.xml`` quand le dossier est
        joignable, du nom de dossier sinon. C'est ce qui garantit qu'un
        ``<subcase>`` du parent et le dossier du sous-cas portent **le même**
        alias : sans cela, un squelette anonymisé perdrait ses correspondances.
        """
        if not self.actif or not chemin:
            return chemin
        cle = ""
        case_xml = os.path.join(chemin, "case.xml")
        if os.path.isfile(case_xml):
            try:
                cle = (ET.parse(case_xml).getroot().findtext("name") or "").strip()
            except (ET.ParseError, OSError):
                cle = ""
        cle = cle or os.path.basename(chemin.rstrip(SEPARATEURS)) or chemin
        return os.path.join(DOSSIER_FICTIF, self.cas(cle))

    def chemin_preuve(self, chemin: str) -> str:
        """Chemin d'évidence : garde la FORME (UNC ou lettre, profondeur, extension).

        ``path_parser`` et la détection de segment non initial se testent sur ces
        formes-là ; les noms réels, eux, n'apportent rien.
        """
        if not self.actif or not chemin:
            return chemin
        unc = chemin.startswith("\\\\")
        morceaux = [m for m in re.split(r"[\\/]+", chemin) if m]
        if unc:
            morceaux = morceaux[2:]          # serveur et partage remplacés en bloc
        elif morceaux and morceaux[0].endswith(":"):
            morceaux = morceaux[1:]
        if not morceaux:
            return chemin
        feuille = morceaux[-1]
        _racine, ext = os.path.splitext(feuille)
        rendu = ["N{}".format(i + 1) for i in range(len(morceaux) - 1)]
        rendu.append("fichier_{}{}".format(len(morceaux), ext))
        tete = "\\\\SERVEUR\\PARTAGE" if unc else "D:\\Preuves"
        return tete + "\\" + "\\".join(rendu)

    def valeurs_sensibles(self) -> list[str]:
        """Toutes les valeurs d'origine substituées (pour la vérification finale)."""
        return [v for famille, table in self._tables.items()
                for v in table if famille in ("cas", "user", "source")]


# --------------------------------------------------------------------------- #
# Traitement des fichiers                                                      #
# --------------------------------------------------------------------------- #
def _txt(elem, tag: str) -> str:
    fils = elem.find(tag)
    return (fils.text or "").strip() if fils is not None and fils.text else ""


def _pose(elem, tag: str, valeur: str) -> None:
    fils = elem.find(tag)
    if fils is not None:
        fils.text = valeur


def traiter_case_xml(src: str, dst: str, ano: Anonymiseur) -> dict:
    """Copie un ``case.xml`` (anonymisé ou non) et renvoie ce qu'il déclare.

    Retour : ``{"name", "compound", "subcases": [chemins d'origine]}``.
    """
    arbre = ET.parse(src)
    racine = arbre.getroot()
    nom = _txt(racine, "name")
    compound = (racine.get("compound", "") or "").strip().lower() == "true"
    subcases = []
    bloc = racine.find("subcases")
    if bloc is not None:
        subcases = [(el.text or "").strip() for el in bloc.findall("subcase")
                    if el.text and el.text.strip()]

    if ano.actif:
        if racine.get("id"):
            racine.set("id", ano.identifiant(racine.get("id")))
        _pose(racine, "name", ano.cas(nom))
        _pose(racine, "user", ano.user(_txt(racine, "user")))
        _pose(racine, "description", ano.texte_libre(_txt(racine, "description")))
        for champ in ("fingerprint", "reverseProxyPath", "serverKey"):
            valeur = _txt(racine, champ)
            if valeur:
                _pose(racine, champ, ano.identifiant(valeur))
        if bloc is not None:
            for el in bloc.findall("subcase"):
                el.text = ano.chemin_cas((el.text or "").strip())

    os.makedirs(os.path.dirname(dst), exist_ok=True)
    arbre.write(dst, encoding="UTF-8", xml_declaration=True)
    return {"name": nom, "compound": compound, "subcases": subcases}


def traiter_prefs(src: str, dst: str, ano: Anonymiseur) -> None:
    """``case.prefs`` : lignes clé=valeur. Seuls les utilisateurs et chemins bougent."""
    lignes = []
    with io.open(src, encoding="utf-8", errors="replace") as f:
        for ligne in f:
            brute = ligne.rstrip("\n")
            if ano.actif and "=" in brute and not brute.lstrip().startswith("#"):
                cle, valeur = brute.split("=", 1)
                cle_nue, valeur = cle.strip(), valeur.strip()
                if cle_nue == "InitialAuthorizedUsers":
                    valeur = ",".join(ano.user(u.strip()) for u in valeur.split(",") if u.strip())
                elif cle_nue.endswith("Path") and valeur:
                    valeur = ano.chemin_preuve(valeur)
                brute = "{}={}".format(cle_nue, valeur)
            lignes.append(brute)
    os.makedirs(os.path.dirname(dst), exist_ok=True)
    with io.open(dst, "w", encoding="utf-8", newline="\n") as f:
        f.write("\n".join(lignes) + "\n")


def traiter_tasks2(src: str, dst: str, ano: Anonymiseur) -> int:
    """``tasks2.json`` : tableau de tâches. Renvoie le nombre de tâches copiées."""
    with io.open(src, encoding="utf-8", errors="replace") as f:
        data = json.load(f)
    if ano.actif and isinstance(data, list):
        for tache in data:
            if not isinstance(tache, dict):
                continue
            if tache.get("name"):
                tache["name"] = ano.tache(tache["name"])
            if tache.get("id"):
                tache["id"] = ano.identifiant(tache["id"])
    os.makedirs(os.path.dirname(dst), exist_ok=True)
    with io.open(dst, "w", encoding="utf-8", newline="\n") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    return len(data) if isinstance(data, list) else 0


def traiter_sources_xml(src: str, dst: str, ano: Anonymiseur) -> int:
    """Export ``-exportSourceList`` : noms et chemins substitués, le reste gardé.

    Tailles, fuseaux, ``partsCount``, ``indexOptions`` et ``domainBoundaries``
    sont **conservés tels quels** : ce sont eux que l'outil exploite (garde-fou de
    volume, « Info Profil »), et ils ne disent rien du contenu des preuves.
    """
    arbre = ET.parse(src)
    racine = arbre.getroot()
    sources = racine.findall("source")
    if not ano.actif:
        os.makedirs(os.path.dirname(dst), exist_ok=True)
        shutil.copyfile(src, dst)
        return len(sources)

    if racine.find("caseName") is not None:
        _pose(racine, "caseName", ano.cas(_txt(racine, "caseName")))
    if racine.find("caseId") is not None:
        _pose(racine, "caseId", ano.identifiant(_txt(racine, "caseId")))
    if racine.find("casePath") is not None:
        _pose(racine, "casePath", ano.chemin_cas(_txt(racine, "casePath")))

    for elem in sources:
        _pose(elem, "name", ano.source(_txt(elem, "name")))
        valeur = _txt(elem, "diskImagePath")
        if valeur:
            _pose(elem, "diskImagePath", ano.chemin_preuve(valeur))
        valeur = _txt(elem, "firstPartName")
        if valeur:
            _pose(elem, "firstPartName", ano.nom_fichier(valeur))
        for chemin in elem.findall("path"):
            if chemin.text and chemin.text.strip():
                chemin.text = ano.chemin_preuve(chemin.text.strip())
        # ``tasks`` porte un tableau JSON (id + name) dans le texte de la balise.
        taches = elem.find("tasks")
        if taches is not None and (taches.text or "").strip():
            taches.text = _anonymiser_taches_json(taches.text, ano)

    os.makedirs(os.path.dirname(dst), exist_ok=True)
    arbre.write(dst, encoding="UTF-8", xml_declaration=True)
    return len(sources)


def _anonymiser_taches_json(brut: str, ano: Anonymiseur) -> str:
    try:
        objs = json.loads(brut)
    except ValueError:
        return "[]"          # illisible : mieux vaut vide que du texte non traité
    for obj in objs if isinstance(objs, list) else []:
        if not isinstance(obj, dict):
            continue
        if obj.get("name"):
            obj["name"] = ano.tache(obj["name"])
        if obj.get("id"):
            obj["id"] = ano.identifiant(obj["id"])
    return json.dumps(objs, ensure_ascii=False)


def traiter_info(src: str, dst: str, ano: Anonymiseur) -> None:
    """``IF_<cas>.info`` : cache de tailles indexé par chemin + réglage d'intégrité."""
    with io.open(src, encoding="utf-8", errors="replace") as f:
        data = json.load(f)
    if ano.actif and isinstance(data.get("folder_sizes"), dict):
        data["folder_sizes"] = {ano.chemin_preuve(k).lower(): v
                                for k, v in data["folder_sizes"].items()}
    os.makedirs(os.path.dirname(dst), exist_ok=True)
    with io.open(dst, "w", encoding="utf-8", newline="\n") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def traiter_ini(src: str, dst: str, ano: Anonymiseur) -> None:
    """``.ini`` : les valeurs qui ressemblent à un chemin ou à un nom de cas."""
    lignes = []
    with io.open(src, encoding="utf-8", errors="replace") as f:
        for ligne in f:
            brute = ligne.rstrip("\n")
            depouille = brute.strip()
            if (ano.actif and "=" in depouille
                    and not depouille.startswith(("#", ";", "["))):
                cle, valeur = depouille.split("=", 1)
                cle_nue, valeur = cle.strip(), valeur.strip()
                if cle_nue in ("last_case", "tasks_path", "output_dir", "venv_path"):
                    valeur = ano.chemin_preuve(valeur) if valeur else valeur
                elif cle_nue == "casename":
                    valeur = ano.cas(valeur)
                elif cle_nue == "user":
                    valeur = ano.user(valeur)
                brute = "{} = {}".format(cle_nue, valeur)
            lignes.append(brute)
    os.makedirs(os.path.dirname(dst), exist_ok=True)
    with io.open(dst, "w", encoding="utf-8", newline="\n") as f:
        f.write("\n".join(lignes) + "\n")


# --------------------------------------------------------------------------- #
# Logs                                                                         #
# --------------------------------------------------------------------------- #
def inventorier_logs(dossier: str, limite: int) -> list[dict]:
    """Nom, taille et nombre de lignes des logs les plus récents. Ne lit aucun texte."""
    if not os.path.isdir(dossier):
        return []
    fichiers = sorted(
        (os.path.join(dossier, n) for n in os.listdir(dossier)
         if os.path.isfile(os.path.join(dossier, n))),
        key=os.path.getmtime, reverse=True)
    releve = []
    for chemin in fichiers[:limite]:
        lignes = 0
        with io.open(chemin, "rb") as f:
            for _ in f:
                lignes += 1
        releve.append({"nom": os.path.basename(chemin),
                       "octets": os.path.getsize(chemin), "lignes": lignes})
    return releve


def copier_logs(dossier: str, dst: str, limite: int, max_ko: int) -> list[dict]:
    """Copie les ``limite`` logs les plus récents, tronqués à ``max_ko`` kilo-octets.

    Réservé au mode ``--brut`` : un log est du texte libre, rien n'y garantit
    l'absence de noms de fichiers, de chemins ou d'adresses réels.
    """
    if not os.path.isdir(dossier):
        return []
    fichiers = sorted(
        (os.path.join(dossier, n) for n in os.listdir(dossier)
         if os.path.isfile(os.path.join(dossier, n))),
        key=os.path.getmtime, reverse=True)[:limite]
    os.makedirs(dst, exist_ok=True)
    copies = []
    plafond = max_ko * 1024
    for chemin in fichiers:
        cible = os.path.join(dst, os.path.basename(chemin))
        taille = os.path.getsize(chemin)
        with io.open(chemin, "rb") as entree, io.open(cible, "wb") as sortie:
            sortie.write(entree.read(plafond))
            if taille > plafond:
                sortie.write("\n[squelette_cas] tronque a {} Ko sur {} Ko\n"
                             .format(max_ko, taille // 1024).encode("utf-8"))
        copies.append({"nom": os.path.basename(chemin), "octets": taille,
                       "tronque": taille > plafond})
    return copies


# --------------------------------------------------------------------------- #
# Parcours d'un cas                                                            #
# --------------------------------------------------------------------------- #
def copier_cas(src: str, racine_dst: str, ano: Anonymiseur, options,
               profondeur: int = 0, vus: set | None = None) -> dict:
    """Copie un cas et, s'il est compound, descend dans chacun de ses sous-cas.

    Un sous-cas injoignable n'interrompt rien : il est reporté. C'est le cas
    courant hors du réseau du laboratoire, et c'est précisément un scénario que
    le squelette doit savoir représenter.
    """
    vus = vus if vus is not None else set()
    cle = os.path.normcase(os.path.abspath(src))
    if cle in vus or profondeur > MAX_PROFONDEUR:
        return {"chemin": ano.chemin_cas(src) if ano.actif else src,
                "etat": "deja vu ou trop profond", "sous_cas": []}
    vus.add(cle)

    # Le chemin lui-meme est une donnee (partage interne, nom de cas) : ce qui
    # sort dans la console et le manifeste passe par l'alias, y compris pour un
    # sous-cas en echec -- c'est justement le cas ou l'on n'a pas pu lire son nom.
    rapport = {"chemin": ano.chemin_cas(src) if ano.actif else src,
               "etat": "ok", "nom": "", "compound": False,
               "fichiers": [], "logs": [], "sous_cas": []}

    if not os.path.isdir(src):
        rapport["etat"] = "dossier introuvable"
        return rapport
    if not os.path.isfile(os.path.join(src, CASE_XML)):
        rapport["etat"] = "pas de case.xml"
        return rapport

    # Le dossier de destination porte l'alias du cas : un squelette anonymisé ne
    # doit pas trahir par ses noms de dossiers ce qu'il masque dans les fichiers.
    infos_provisoires = ET.parse(os.path.join(src, CASE_XML)).getroot()
    nom_reel = (infos_provisoires.findtext("name") or os.path.basename(src)).strip()
    nom_dossier = ano.cas(nom_reel) if ano.actif else os.path.basename(src.rstrip("\\/"))
    dst = os.path.join(racine_dst, _assainir(nom_dossier))

    infos = traiter_case_xml(os.path.join(src, CASE_XML), os.path.join(dst, CASE_XML), ano)
    rapport["nom"] = ano.cas(infos["name"]) if ano.actif else infos["name"]
    rapport["compound"] = infos["compound"]
    rapport["fichiers"].append(CASE_XML)

    prefs = os.path.join(src, PREFS_DIR, CASE_PREFS)
    if os.path.isfile(prefs):
        traiter_prefs(prefs, os.path.join(dst, PREFS_DIR, CASE_PREFS), ano)
        rapport["fichiers"].append(PREFS_DIR + "/" + CASE_PREFS)

    tasks2 = os.path.join(src, PREFS_DIR, TASKS2_JSON)
    if os.path.isfile(tasks2):
        nb = traiter_tasks2(tasks2, os.path.join(dst, PREFS_DIR, TASKS2_JSON), ano)
        rapport["fichiers"].append("{}/{} ({} tache(s))".format(PREFS_DIR, TASKS2_JSON, nb))

    for nom in sorted(os.listdir(src)):
        chemin = os.path.join(src, nom)
        if not os.path.isfile(chemin) or nom == CASE_XML:
            continue
        bas = nom.lower()
        if bas.endswith(".xml"):
            nb = traiter_sources_xml(chemin, os.path.join(dst, nom), ano)
            rapport["fichiers"].append("{} ({} source(s))".format(nom, nb))
        elif bas.endswith(".info"):
            # Le nom du fichier porte celui du cas (IF_<cas>.info) : l'anonymat
            # se perdrait par le nom de fichier, que le contenu soit propre ou non.
            cible = "IF_{}.info".format(ano.cas(nom[3:-5])) if (
                ano.actif and nom.startswith("IF_")) else nom
            traiter_info(chemin, os.path.join(dst, cible), ano)
            rapport["fichiers"].append(cible)
        elif bas.endswith(".ini"):
            traiter_ini(chemin, os.path.join(dst, nom), ano)
            rapport["fichiers"].append(nom)

    dossier_logs = os.path.join(src, LOGS_DIR)
    if options.logs == "brut":
        rapport["logs"] = copier_logs(dossier_logs, os.path.join(dst, LOGS_DIR),
                                      options.nb_logs, options.max_log_ko)
    elif options.logs == "inventaire":
        rapport["logs"] = inventorier_logs(dossier_logs, options.nb_logs)

    if infos["compound"]:
        for chemin_sub in infos["subcases"]:
            rapport["sous_cas"].append(
                copier_cas(chemin_sub, racine_dst, ano, options, profondeur + 1, vus))
    return rapport


def _assainir(nom: str) -> str:
    return re.sub(r'[<>:"/\\|?*]', "_", nom).strip() or "CAS"


# --------------------------------------------------------------------------- #
# Vérification et manifeste                                                    #
# --------------------------------------------------------------------------- #
def verifier_anonymat(dossier: str, ano: Anonymiseur) -> list[str]:
    """Relit le squelette et signale toute valeur d'origine qui y subsisterait.

    Garde-fou volontairement paranoïaque : un squelette anonymisé n'a d'intérêt
    que si l'on peut le lire sans réfléchir. Mieux vaut un faux positif qu'une
    valeur oubliée dans un champ non prévu.
    """
    sensibles = [v for v in ano.valeurs_sensibles() if len(v) >= 4]
    if not sensibles:
        return []
    fuites = []
    for racine, dossiers, fichiers in os.walk(dossier):
        # Un nom de fichier ou de dossier trahit aussi bien qu'un contenu :
        # `IF_<cas>.info` a failli passer entre les mailles.
        for nom in dossiers + fichiers:
            for valeur in sensibles:
                if valeur in nom:
                    fuites.append("nom : {}".format(
                        os.path.relpath(os.path.join(racine, nom), dossier)))
        for nom in fichiers:
            if nom == MANIFESTE:
                continue
            chemin = os.path.join(racine, nom)
            try:
                with io.open(chemin, encoding="utf-8", errors="replace") as f:
                    contenu = f.read()
            except OSError:
                continue
            for valeur in sensibles:
                if valeur in contenu:
                    fuites.append("{} : « {} »".format(
                        os.path.relpath(chemin, dossier), valeur[:20]))
    return fuites


def _lignes_rapport(rapport: dict, niveau: int = 0) -> list[str]:
    marge = "  " * niveau
    if rapport["etat"] != "ok":
        return ["{}- [X] `{}` - **{}**".format(marge, rapport["chemin"], rapport["etat"])]
    lignes = ["{}- **{}**{}".format(marge, rapport["nom"],
                                    " *(compound)*" if rapport["compound"] else "")]
    for f in rapport["fichiers"]:
        lignes.append("{}  - {}".format(marge, f))
    if rapport["logs"]:
        total = sum(l["octets"] for l in rapport["logs"])
        lignes.append("{}  - logs : {} fichier(s), {} Ko au total".format(
            marge, len(rapport["logs"]), total // 1024))
    for sous in rapport["sous_cas"]:
        lignes += _lignes_rapport(sous, niveau + 1)
    return lignes


def ecrire_manifeste(dossier: str, rapport: dict, ano: Anonymiseur,
                     options, fuites: list[str]) -> None:
    mode = "BRUT (données réelles)" if not ano.actif else "anonymisé"
    lignes = [
        "# Squelette de cas — IntellaFeeder",
        "",
        "Produit par `outils/squelette_cas.py`. **Jeu d'essai** : ne pas confondre",
        "avec un cas Intella exploitable (aucune preuve, aucun index).",
        "",
        "- Mode : **{}**".format(mode),
        "- Logs : {}".format(options.logs),
        "",
    ]
    if not ano.actif:
        lignes += [
            "> ⚠ **Ce squelette contient des données réelles** (noms de cas,",
            "> utilisateurs, chemins, et le contenu des logs copiés). Le traiter",
            "> comme le cas d'origine : ne pas le diffuser, ne pas le donner à lire",
            "> à un outil tiers. Relancer sans `--brut` pour une version diffusable.",
            "",
        ]
    lignes += ["## Contenu", ""] + _lignes_rapport(rapport) + [""]
    if ano.actif:
        lignes += ["## Vérification d'anonymat", ""]
        if fuites:
            lignes += ["✕ **{} valeur(s) d'origine retrouvée(s)** :".format(len(fuites)), ""]
            lignes += ["- {}".format(f) for f in fuites] + [""]
        else:
            lignes += ["✓ Aucune valeur d'origine retrouvée dans les fichiers produits.", ""]
    with io.open(os.path.join(dossier, MANIFESTE), "w", encoding="utf-8", newline="\n") as f:
        f.write("\n".join(lignes))


# --------------------------------------------------------------------------- #
class Options:
    """Réglages d'une fabrication, hors ligne de commande.

    Même jeu de champs que le ``Namespace`` d'argparse : l'interface graphique
    et le CLI passent par ``valider`` puis ``fabriquer`` avec le même objet, ce
    qui interdit à l'un de desserrer un garde-fou que l'autre applique.
    """

    def __init__(self, cas="", sortie="", brut=False, logs="inventaire",
                 nb_logs=5, max_log_ko=256, force=False):
        self.cas = cas
        self.sortie = sortie
        self.brut = brut
        self.logs = logs
        self.nb_logs = nb_logs
        self.max_log_ko = max_log_ko
        self.force = force


def valider(options) -> str:
    """Contrôles préalables. Renvoie le motif du refus, ou "" si tout va bien.

    Le premier contrôle n'est pas une commodité : copier des logs revient à
    copier du texte libre non anonymisable, ce qui doit rester un choix explicite
    et non l'effet de bord d'une case cochée.
    """
    if options.logs == "brut" and not options.brut:
        return ("Copier les logs revient a copier du texte libre, qui ne "
                "s'anonymise pas de facon fiable : cochez aussi le mode brut "
                "pour l'assumer explicitement.")
    if not os.path.isdir(options.cas):
        return "Dossier de cas introuvable : {}".format(options.cas)
    if not os.path.isfile(os.path.join(options.cas, CASE_XML)):
        return "Pas un dossier de cas Intella (case.xml absent) : {}".format(options.cas)
    if not options.sortie:
        return "Indiquez un dossier de sortie."
    if (os.path.isdir(options.sortie) and os.listdir(options.sortie)
            and not options.force):
        return "Dossier de sortie non vide : {}".format(options.sortie)
    return ""


def fabriquer(options):
    """Enchaînement complet : copie, vérification d'anonymat, manifeste.

    Point d'entrée unique des deux interfaces — la vérification d'anonymat ne
    doit pas pouvoir être sautée par l'une d'elles.
    """
    os.makedirs(options.sortie, exist_ok=True)
    ano = Anonymiseur(actif=not options.brut)
    rapport = copier_cas(options.cas, options.sortie, ano, options)
    fuites = verifier_anonymat(options.sortie, ano) if ano.actif else []
    ecrire_manifeste(options.sortie, rapport, ano, options, fuites)
    return rapport, fuites


def main(argv=None) -> int:
    # Alias et chemins peuvent sortir du cp1252 de la console Windows : on force
    # UTF-8 plutot que de laisser un UnicodeEncodeError tuer un traitement reussi.
    for flux in (sys.stdout, sys.stderr):
        try:
            flux.reconfigure(encoding="utf-8", errors="replace")
        except (AttributeError, OSError):
            pass
    parseur = argparse.ArgumentParser(
        description="Fabrique un squelette de test à partir d'un cas Intella.")
    parseur.add_argument("cas", help="dossier du cas source (compound ou non)")
    parseur.add_argument("sortie", help="dossier de destination (créé au besoin)")
    parseur.add_argument("--brut", action="store_true",
                         help="copie à l'identique, sans anonymiser (données réelles)")
    parseur.add_argument("--logs", choices=("aucun", "inventaire", "brut"),
                         default="inventaire",
                         help="logs : inventoriés (défaut), ignorés, ou copiés (--brut requis)")
    parseur.add_argument("--nb-logs", type=int, default=5, dest="nb_logs",
                         help="nombre de logs les plus récents à traiter (défaut : 5)")
    parseur.add_argument("--max-log-ko", type=int, default=256, dest="max_log_ko",
                         help="troncature des logs copiés, en Ko (défaut : 256)")
    parseur.add_argument("--force", action="store_true",
                         help="écraser un dossier de sortie non vide")
    options = parseur.parse_args(argv)

    refus = valider(options)
    if refus:
        complement = ""
        if refus.startswith("Dossier de sortie non vide"):
            complement = " (--force pour écraser)"
        print(refus + complement, file=sys.stderr)
        return 2

    rapport, fuites = fabriquer(options)

    print("\n".join(_lignes_rapport(rapport)))
    print("\nSquelette écrit dans : {}".format(os.path.abspath(options.sortie)))
    print("Manifeste : {}".format(os.path.join(options.sortie, MANIFESTE)))
    if fuites:
        print("\n[!] {} valeur(s) d'origine retrouvee(s) dans le squelette "
              "(voir le manifeste).".format(len(fuites)), file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
