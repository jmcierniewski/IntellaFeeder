# -*- coding: utf-8 -*-
"""Regenere ``lang_data.py`` a partir de ``lang/FR.lang`` et ``lang/US.lang``.

    python outils\\gen_lang_data.py

Pourquoi un outil plutot qu'un script jetable a chaque fois : la regeneration
"a la main" a deja perdu deux choses, et chacune coute une session.

1. **Le ``r`` du docstring.** Le module explique le role du dossier ``lang\\`` ;
   ecrit dans un docstring ordinaire, ce ``\\l`` devient une sequence
   d'echappement inconnue et Python emet un ``SyntaxWarning``. D'ou le prefixe
   ``r`` -- et d'ou le fait que l'en-tete soit compose ici, pas recopie.
2. **Le format.** ``json.dumps(..., ensure_ascii=False, indent=4)`` est celui du
   fichier existant. ``pprint.pformat`` marche aussi mais reformate les ~1600
   lignes : le diff d'un simple ajout de cle devient illisible.

Le JSON des deux langues ne contient ni ``true``/``false`` ni ``null`` (verifie
ci-dessous) : sa serialisation est donc un litteral Python valide tel quel.
"""

import json
import os
import sys

RACINE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
LANG_DIR = os.path.join(RACINE, "lang")
CIBLE = os.path.join(RACINE, "lang_data.py")
LANGUES = ("FR", "US")

# Compose pour ne pas fermer le docstring de CE module (piege rencontre en
# ecrivant `gen_mime_data.py` : un `"""` litteral dans un docstring produit une
# SyntaxError trompeuse, qui pointe une ligne sans rapport).
_Q = chr(34) * 3

EN_TETE = '''r{q}Traductions embarquees dans l'executable (module .py, pas un fichier de donnees).

Ce module contient les langues **integrees** (FR, US) : PyInstaller les embarque
comme n'importe quel module source -- pas de ``--add-data``, pas de dossier
externe requis pour que l'appli fonctionne des sa premiere installation. Elle
tourne donc en FR/US meme si le dossier ``lang\\`` n'existe pas du tout a cote
de l'exe.

Un fichier externe ``lang\\<CODE>.lang`` (JSON, meme structure : ``strings`` +
``help``) reste possible et est **toujours prioritaire** sur son equivalent
integre ici -- pratique pour corriger une traduction ou ajouter une langue sans
reconstruire l'exe (voir ``i18n._read``). ``lang/FR.lang`` et ``lang/US.lang``
peuvent etre conserves a cote du script pour l'edition ; ils sont facultatifs
une fois l'exe construit.

Genere par ``outils/gen_lang_data.py`` a partir de ``lang/FR.lang`` et
``lang/US.lang`` -- si ces .lang evoluent et que l'evolution doit etre
embarquee, relancer cet outil (voir CLAUDE.md).
{q}

BUILTIN = '''.format(q=_Q)


def _interdits(valeur, chemin=""):
    """Chemins des valeurs qui ne se serialisent pas en litteral Python.

    ``True``/``False``/``None`` s'ecrivent ``true``/``false``/``null`` en JSON :
    presents, ils rendraient le module genere invalide. Aucune traduction n'en
    contient aujourd'hui -- on le verifie plutot que de le supposer.
    """
    if isinstance(valeur, bool) or valeur is None:
        return [chemin or "<racine>"]
    if isinstance(valeur, dict):
        trouves = []
        for cle, sous in valeur.items():
            trouves += _interdits(sous, "%s/%s" % (chemin, cle))
        return trouves
    if isinstance(valeur, list):
        trouves = []
        for i, sous in enumerate(valeur):
            trouves += _interdits(sous, "%s[%d]" % (chemin, i))
        return trouves
    return []


def main():
    data = {}
    for code in LANGUES:
        chemin = os.path.join(LANG_DIR, code + ".lang")
        with open(chemin, encoding="utf-8") as fh:
            data[code] = json.load(fh)
        print("%s : %d chaines, %d blocs d'aide"
              % (code, len(data[code].get("strings", {})),
                 len(data[code].get("help", []))))

    mauvais = _interdits(data)
    if mauvais:
        print("ABANDON : valeurs bool/null non serialisables en litteral Python :")
        for chemin in mauvais:
            print("   " + chemin)
        return 1

    corps = json.dumps(data, ensure_ascii=False, indent=4)
    with open(CIBLE, "w", encoding="utf-8", newline="\n") as fh:
        fh.write(EN_TETE + corps + "\n")

    # Relecture : le module doit s'importer et rendre exactement les memes
    # donnees. Un generateur qui ne se relit pas laisse passer sa propre panne.
    sys.path.insert(0, RACINE)
    for module in ("lang_data",):
        sys.modules.pop(module, None)
    import lang_data
    assert lang_data.BUILTIN == data, "le module genere ne relit pas ses donnees"
    print("Ecrit : %s (%d lignes)"
          % (CIBLE, sum(1 for _ in open(CIBLE, encoding="utf-8"))))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
