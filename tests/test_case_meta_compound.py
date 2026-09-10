"""Cas compound : détection, sous-cas référencés, utilisateurs autorisés.

Un cas compound ne contient aucune source en propre : il référence des sous-cas
(chemins ABSOLUS), porte la taille TOTALE de l'ensemble et n'accepte pas
``-addSourcesFromJson``. Les ``case.xml`` de ces tests sont **fabriqués** : la
forme est celle constatée sur un compound réel (attribut ``compound="true"`` +
bloc ``<subcases>``), sans aucune donnée de cas.

Régression verrouillée : un sous-cas déclaré mais absent du poste (partage
démonté, compound recopié seul) doit rester une ligne signalée — jamais une
exception, sinon l'onglet Inventaire refuserait d'ouvrir le compound entier.
"""

import io
import os

import case_meta

CASE_TPL = """<?xml version="1.0" encoding="UTF-8"?>
<case version="3.1" id="{cid}"{compound_attr}>
  <name>{name}</name>
  <description>{desc}</description>
  <timestamp>1750000000000</timestamp>
  <lastOpened>1760000000000</lastOpened>
  <user>{user}</user>
  <size>{size}</size>
  <originalVersion>3.1</originalVersion>
  <caseVersion>3.1</caseVersion>
{subcases}</case>
"""


def write_case(folder, name="Cas", user="op1", size=1024, subcases=None,
               compound=False, cid="0000-1111", desc="essai"):
    """Écrit un ``case.xml`` fabriqué dans ``folder`` (créé au besoin)."""
    os.makedirs(folder, exist_ok=True)
    block = ""
    if subcases is not None:
        lignes = "".join(f"    <subcase>{p}</subcase>\n" for p in subcases)
        block = f"  <subcases>\n{lignes}  </subcases>\n"
    xml = CASE_TPL.format(cid=cid, name=name, desc=desc, user=user, size=size,
                          compound_attr=' compound="true"' if compound else "",
                          subcases=block)
    with io.open(os.path.join(folder, "case.xml"), "w", encoding="utf-8") as f:
        f.write(xml)
    return folder


def write_prefs(folder, users):
    os.makedirs(os.path.join(folder, "prefs"), exist_ok=True)
    with io.open(os.path.join(folder, "prefs", "case.prefs"), "w", encoding="utf-8") as f:
        f.write("MessageHashingAlgorithm=SHA256\n")
        f.write(f"InitialAuthorizedUsers={users}\n")


class TestDetection:
    def test_cas_simple_nest_pas_compound(self, tmp_path):
        folder = write_case(str(tmp_path / "simple"))
        xml = case_meta.read_case_xml(folder)
        assert xml["compound"] is False and xml["subcase_paths"] == []

    def test_cas_compound_detecte(self, tmp_path):
        folder = write_case(str(tmp_path / "comp"), compound=True,
                            subcases=[r"D:\a\sub1", r"D:\a\sub2"])
        xml = case_meta.read_case_xml(folder)
        assert xml["compound"] is True
        assert xml["subcase_paths"] == [r"D:\a\sub1", r"D:\a\sub2"]

    def test_bloc_subcases_vide(self, tmp_path):
        folder = write_case(str(tmp_path / "vide"), compound=True, subcases=[])
        assert case_meta.read_case_xml(folder)["subcase_paths"] == []

    def test_read_case_expose_le_type(self, tmp_path):
        simple = write_case(str(tmp_path / "s"))
        assert case_meta.read_case(simple)["is_compound"] is False
        assert case_meta.read_case(simple)["subcases"] == []


class TestUtilisateursAutorises:
    def test_liste_csv_nettoyee(self):
        prefs = {"InitialAuthorizedUsers": " a , b ,, c "}
        assert case_meta.authorized_users(prefs) == ["a", "b", "c"]

    def test_absent_ou_vide(self):
        assert case_meta.authorized_users({}) == []
        assert case_meta.authorized_users({"InitialAuthorizedUsers": ""}) == []

    def test_expose_par_read_case(self, tmp_path):
        folder = write_case(str(tmp_path / "c"))
        write_prefs(folder, "alice,bob")
        assert case_meta.read_case(folder)["authorized_users"] == ["alice", "bob"]


class TestReadSubcases:
    def test_sous_cas_lisible(self, tmp_path):
        sub = write_case(str(tmp_path / "sub1"), name="Sous-cas 1", user="op2", size=4096)
        write_prefs(sub, "alice,bob")
        parent = write_case(str(tmp_path / "comp"), compound=True, subcases=[sub])

        (entry,) = case_meta.read_subcases(parent)
        assert entry["exists"] is True
        assert entry["name"] == "Sous-cas 1"
        assert entry["user"] == "op2"
        assert entry["size"] == 4096
        assert entry["authorized_users"] == ["alice", "bob"]
        assert entry["error"] == ""

    def test_dossier_absent_signale_sans_lever(self, tmp_path):
        manquant = str(tmp_path / "pas_la")
        parent = write_case(str(tmp_path / "comp"), compound=True, subcases=[manquant])

        (entry,) = case_meta.read_subcases(parent)
        assert entry["exists"] is False
        assert entry["error"]
        # Repli d'affichage : le nom du dossier, faute de case.xml lisible.
        assert entry["name"] == "pas_la"

    def test_dossier_sans_case_xml(self, tmp_path):
        vide = tmp_path / "sub_vide"
        vide.mkdir()
        parent = write_case(str(tmp_path / "comp"), compound=True, subcases=[str(vide)])

        (entry,) = case_meta.read_subcases(parent)
        assert entry["exists"] is False and "case.xml" in entry["error"]

    def test_case_xml_illisible(self, tmp_path):
        casse = tmp_path / "sub_casse"
        casse.mkdir()
        with io.open(casse / "case.xml", "w", encoding="utf-8") as f:
            f.write("<case><name>tronqu")
        parent = write_case(str(tmp_path / "comp"), compound=True, subcases=[str(casse)])

        (entry,) = case_meta.read_subcases(parent)
        assert entry["exists"] is False and entry["error"]

    def test_melange_lisible_et_manquant(self, tmp_path):
        ok = write_case(str(tmp_path / "ok"), name="OK", size=10)
        ko = str(tmp_path / "ko")
        parent = write_case(str(tmp_path / "comp"), compound=True, subcases=[ok, ko],
                            size=10)
        entries = case_meta.read_subcases(parent)
        assert [e["exists"] for e in entries] == [True, False]

    def test_subcase_relatif_resolu_depuis_le_compound(self, tmp_path, monkeypatch):
        """Un `<subcase>` relatif se lit depuis le dossier du COMPOUND.

        Le resoudre depuis le repertoire courant rendrait le resultat dependant
        de l'endroit d'ou l'application a ete lancee — un compound portable
        serait declare introuvable une fois sur deux.
        """
        racine = tmp_path / "lot"
        write_case(str(racine / "sub"), name="Volet 1", size=42)
        parent = write_case(str(racine / "comp"), compound=True,
                            subcases=[os.path.join("..", "sub")])
        monkeypatch.chdir(tmp_path.parent)      # cwd volontairement ailleurs

        (entry,) = case_meta.read_subcases(parent)
        assert entry["exists"] is True
        assert entry["name"] == "Volet 1" and entry["size"] == 42

    def test_compound_portable_apres_deplacement(self, tmp_path):
        """Des `<subcase>` relatifs survivent a une recopie du lot ailleurs."""
        import shutil
        lot = tmp_path / "lot"
        write_case(str(lot / "sub"), name="Volet 1")
        write_case(str(lot / "comp"), compound=True,
                   subcases=[os.path.join("..", "sub")])
        ailleurs = tmp_path / "autre" / "lot"
        shutil.copytree(str(lot), str(ailleurs))

        (entry,) = case_meta.read_subcases(str(ailleurs / "comp"))
        assert entry["exists"] is True

    def test_subcase_absolu_reste_absolu(self, tmp_path):
        """Le cas courant (chemins absolus) ne doit pas changer de comportement."""
        sub = write_case(str(tmp_path / "sub"), name="Volet abs")
        parent = write_case(str(tmp_path / "comp"), compound=True, subcases=[sub])
        (entry,) = case_meta.read_subcases(parent)
        assert entry["exists"] is True and os.path.isabs(entry["path"])

    def test_declared_path_conserve(self, tmp_path):
        """Le chemin écrit dans le case.xml reste disponible (repli, affichage)."""
        sub = write_case(str(tmp_path / "sub"), name="S1")
        parent = write_case(str(tmp_path / "comp"), compound=True, subcases=[sub])
        (entry,) = case_meta.read_subcases(parent)
        assert entry["declared_path"] == entry["path"] == os.path.normpath(sub)

    def test_read_case_peuple_les_sous_cas(self, tmp_path):
        sub = write_case(str(tmp_path / "sub"), name="S1", size=7)
        parent = write_case(str(tmp_path / "comp"), compound=True, subcases=[sub], size=7)
        meta = case_meta.read_case(parent)
        assert meta["is_compound"] is True
        assert [e["name"] for e in meta["subcases"]] == ["S1"]


class TestHoteUncDesSousCas:
    """Sous-cas déclaré par IP alors que le compound est ouvert par son nom.

    Constaté le 07/09/2026 : les deux écritures désignent le même dossier, mais
    Windows en fait deux sessions SMB. Celle de l'IP était lisible et refusée en
    écriture → ``-exportSourceList`` échouait sur ``case.xml.lock``. On préfère
    donc l'hôte du compound, à condition qu'il désigne bien un dossier.
    """
    COMPOUND = "\\\\SERVEUR_CAS\\partage\\CAS CP"
    DECLARE = "\\\\192.0.2.174\\partage\\CAS (2)"
    ALIGNE = "\\\\SERVEUR_CAS\\partage\\CAS (2)"

    def _isdir(self, monkeypatch, presents):
        """Faux système de fichiers : ces UNC n'existent nulle part.

        ``has_case_xml`` est neutralisé avec ``isdir`` — sans cela, la recherche
        de ``case.xml`` partirait interroger un hôte inexistant sur le réseau
        (~10 s de timeout par chemin), ce que la suite s'interdit.
        """
        monkeypatch.setattr(case_meta.os.path, "isdir", lambda p: p in presents)
        monkeypatch.setattr(case_meta, "has_case_xml", lambda p: False)

    def test_hote_du_compound_prefere(self, monkeypatch):
        self._isdir(monkeypatch, {self.COMPOUND, self.DECLARE, self.ALIGNE})
        (entry,) = case_meta.read_subcases(self.COMPOUND, [self.DECLARE])
        assert entry["path"] == self.ALIGNE
        assert entry["declared_path"] == self.DECLARE

    def test_hote_aligne_inexistant_on_garde_le_declare(self, monkeypatch):
        self._isdir(monkeypatch, {self.COMPOUND, self.DECLARE})
        (entry,) = case_meta.read_subcases(self.COMPOUND, [self.DECLARE])
        assert entry["path"] == self.DECLARE

    def test_partage_different_non_realigne(self, monkeypatch):
        autre = "\\\\192.0.2.174\\autre\\CAS (2)"
        self._isdir(monkeypatch, {self.COMPOUND, autre,
                                  "\\\\SERVEUR_CAS\\autre\\CAS (2)"})
        (entry,) = case_meta.read_subcases(self.COMPOUND, [autre])
        assert entry["path"] == autre
