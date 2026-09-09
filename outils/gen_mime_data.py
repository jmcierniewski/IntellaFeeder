r"""Génère ``mime_data.py`` — le référentiel de types MIME **embarqué dans l'exe**.

À relancer quand le fichier de descriptions d'Intella change de version, ou
quand la liste des noms observés s'enrichit :

```powershell
python Script\outils\gen_mime_data.py "<...\mimetype-descriptions_en.properties>"
```

Sans argument, reprend ce que contient déjà ``Script\mimetypes\`` (le
``.properties`` le plus récent + ``noms_observes.txt``).

Même contrat que ``lang_data.py`` : un **module Python normal**, embarqué par
PyInstaller sans ``--add-data``, et **toujours dominé par le fichier externe**
s'il existe — corriger un libellé ou ajouter des types ne doit pas exiger une
recompilation.

⚠ Format imposé : ``json.dumps(ensure_ascii=False, indent=4)``, et docstring du
module généré préfixé ``r`` (mêmes pièges que ``lang_data.py`` : une
régénération naïve perd le préfixe et provoque un ``SyntaxWarning`` sur les
antislashs des chemins Windows).
"""

import json
import os
import sys

ICI = os.path.dirname(os.path.abspath(__file__))
SCRIPT = os.path.dirname(ICI)
sys.path.insert(0, SCRIPT)

import mime_catalog  # noqa: E402

CIBLE = os.path.join(SCRIPT, "mime_data.py")

# Le docstring du module généré contient lui-même des `"""` : on le compose par
# morceaux plutôt que d'imbriquer deux niveaux de guillemets triples.
_Q = chr(34) * 3
EN_TETE = "r" + _Q + "\n".join([
    "Référentiel de types MIME **intégré à l'exécutable** (module .py, pas une donnée).",
    "",
    "Généré par ``outils/gen_mime_data.py`` à partir du fichier de descriptions",
    "d'Intella et de ``mimetypes/noms_observes.txt``. PyInstaller l'embarque comme",
    "n'importe quel module source : l'application nomme les types dès sa première",
    "installation, sans dossier ``mimetypes`` ni import préalable.",
    "",
    "Un fichier externe ``mimetypes\\*.properties`` reste **prioritaire** sur",
    "``DESCRIPTIONS`` (voir ``mime_catalog.load``) : une nouvelle version d'Intella",
    "s'absorbe sans recompiler. ``OBSERVED``, lui, **fusionne** avec les noms appris",
    "des cas lus — ce sont des constats, pas une version.",
    "",
    "``DESCRIPTIONS`` : {nom de type: libellé}. La clé **vide** est le type",
    "« Untyped » : ce n'est pas une scorie.",
    "``OBSERVED`` : noms réellement écrits par Intella dans un filtre, alias compris,",
    "que les descriptions ne couvrent pas toujours.",
]) + "\n" + _Q + "\n\n"


def principal(argv):
    source = argv[1] if len(argv) > 1 else ""
    if source:
        with open(source, encoding="latin-1") as fh:
            descriptions, doublons = mime_catalog.parse_properties(fh.read())
    else:
        mime_catalog.load()
        descriptions = dict(mime_catalog._descriptions)
        doublons = mime_catalog._duplicates
        source = mime_catalog.descriptions_path() or "(aucun)"
    if not descriptions:
        print("Aucune description trouvée — rien à générer.", file=sys.stderr)
        return 1

    mime_catalog.load()
    observed = sorted(set(mime_catalog._observed) | set(descriptions))

    corps = (EN_TETE
             + "DESCRIPTIONS = "
             + json.dumps(descriptions, ensure_ascii=False, indent=4, sort_keys=True)
             + "\n\nOBSERVED = "
             + json.dumps(observed, ensure_ascii=False, indent=4)
             + "\n")
    with open(CIBLE, "w", encoding="utf-8") as fh:
        fh.write(corps)

    print(f"source        : {source}")
    print(f"descriptions  : {len(descriptions)}"
          + (f" ({len(set(doublons))} clé(s) en double)" if doublons else ""))
    print(f"noms observés : {len(observed)}")
    print(f"écrit         : {CIBLE}")
    return 0


if __name__ == "__main__":
    raise SystemExit(principal(sys.argv))
