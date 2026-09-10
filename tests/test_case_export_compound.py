"""Inventaire d'un cas compound : un ``-exportSourceList`` par sous-cas.

``run_export_subcases`` orchestre N appels et fusionne. IntellaCmd n'est jamais
lancé ici : ``run_export_source_list`` est remplacé par un faux, ce qui laisse
tester ce qui compte vraiment — la fusion, l'attribution des sources à leur
sous-cas, et surtout la **tolérance aux échecs partiels**.

Contrat verrouillé : un sous-cas en échec n'interrompt pas les autres, mais
l'appelant doit pouvoir dire que l'inventaire est partiel (``subcase_reports``).
Une exception n'est levée que si AUCUN sous-cas n'a pu être lu.
"""

import pytest

import case_export


def sub(name, path, exists=True, error=""):
    return {"name": name, "path": path, "exists": exists, "error": error,
            "user": "", "size": 0, "authorized_users": []}


def fake_export(rows_by_case, taches=None, fail=(), zero=None, case_names=None):
    """Faux ``run_export_source_list`` : réponses figées par chemin de cas.

    ``zero`` : noms des sources « dossier » sans taille reportée par sous-cas
    (celles qui alimentent ``folder_unknown``). ``case_names`` : nom Intella du
    cas tel que le donnerait le XML, quand il diffère du nom du sous-cas.
    """
    def _run(exe, user, case_loc, log, extra_args="", timeout_min=30):
        if case_loc in fail:
            raise RuntimeError("IntellaCmd a renvoyé le code 1")
        noms = rows_by_case[case_loc]
        rows = [{"Nom": n, "Type": "Dossier/Fichier", "Chemin": f"{case_loc}\\{n}"}
                for n in noms]
        inv = {
            "existing_paths": {f"{case_loc}\\{n}".lower() for n in noms},
            "known_bytes": 100 * len(noms),
            "folder_unknown": [{"name": n, "path": f"{case_loc}\\{n}"}
                               for n in (zero or {}).get(case_loc, [])],
            "case_tasks": list((taches or {}).get(case_loc, [])),
            "sources_detail": [{"name": n} for n in noms],
            "xml_path": f"{case_loc}\\sources.xml",
        }
        if case_names and case_loc in case_names:
            inv["case_name"] = case_names[case_loc]
        return rows, list(case_export.DISPLAY_COLUMNS), inv
    return _run


@pytest.fixture
def journal():
    lignes = []
    return lignes, lignes.append


class TestFusion:
    def test_sources_attribuees_a_leur_sous_cas(self, monkeypatch, journal):
        _lines, log = journal
        monkeypatch.setattr(case_export, "run_export_source_list",
                            fake_export({"A": ["s1", "s2"], "B": ["s3"]}))
        rows, columns, inv = case_export.run_export_subcases(
            "x.exe", "u", [sub("Sub A", "A"), sub("Sub B", "B")], log,
            case_name="Compound", case_path="C")

        assert columns[0] == case_export.SUBCASE_COLUMN
        assert [r[case_export.SUBCASE_COLUMN] for r in rows] == ["Sub A", "Sub A", "Sub B"]
        assert inv["source_count"] == 3
        assert inv["known_bytes"] == 300
        assert inv["is_compound"] is True
        assert inv["case_name"] == "Compound"

    def test_detail_porte_le_sous_cas(self, monkeypatch, journal):
        _lines, log = journal
        monkeypatch.setattr(case_export, "run_export_source_list",
                            fake_export({"A": ["s1"], "B": ["s2"]}))
        _rows, _cols, inv = case_export.run_export_subcases(
            "x.exe", "u", [sub("Sub A", "A"), sub("Sub B", "B")], log)
        assert [d["subcase"] for d in inv["sources_detail"]] == ["Sub A", "Sub B"]
        assert [d["subcase_path"] for d in inv["sources_detail"]] == ["A", "B"]

    def test_un_xml_par_sous_cas_lu(self, monkeypatch, journal):
        _lines, log = journal
        monkeypatch.setattr(case_export, "run_export_source_list",
                            fake_export({"A": ["s1"], "B": ["s2"]}))
        _rows, _cols, inv = case_export.run_export_subcases(
            "x.exe", "u", [sub("Sub A", "A"), sub("Sub B", "B")], log)
        assert inv["xml_paths"] == ["A\\sources.xml", "B\\sources.xml"]
        assert inv["xml_path"] == "A\\sources.xml"

    def test_taches_dedupliquees_entre_sous_cas(self, monkeypatch, journal):
        _lines, log = journal
        meme_tache = {"id": "uuid-different", "name": "OCR", "condition": "ALL"}
        autre = dict(meme_tache, id="autre-uuid")
        monkeypatch.setattr(case_export, "run_export_source_list", fake_export(
            {"A": ["s1"], "B": ["s2"]}, taches={"A": [meme_tache], "B": [autre]}))
        _rows, _cols, inv = case_export.run_export_subcases(
            "x.exe", "u", [sub("Sub A", "A"), sub("Sub B", "B")], log)
        # Même signature (l'UUID est hors signature) : une seule tâche retenue.
        assert len(inv["case_tasks"]) == 1


class TestDossiersAZeroRattachesAuSousCas:
    """Chaque dossier sans taille sait de quel sous-cas il vient.

    C'est ce qui permet à l'Inventaire de lire et d'écrire le cache
    `IF_<cas>.info` **dans le sous-cas** et jamais au niveau du compound : la
    composition d'un lot bouge (sous-cas retiré, sources ajoutées), un cache
    unique au niveau du compound survivrait à des cas qui n'existent plus.
    """
    def test_chaque_dossier_porte_son_sous_cas(self, monkeypatch, journal):
        _lines, log = journal
        monkeypatch.setattr(case_export, "run_export_source_list", fake_export(
            {"A": ["s1"], "B": ["s2"]}, zero={"A": ["d1"], "B": ["d2"]}))
        _rows, _cols, inv = case_export.run_export_subcases(
            "x.exe", "u", [sub("Sub A", "A"), sub("Sub B", "B")], log)

        assert [f["subcase"] for f in inv["folder_unknown"]] == ["Sub A", "Sub B"]
        assert [f["subcase_path"] for f in inv["folder_unknown"]] == ["A", "B"]

    def test_nom_de_cas_du_xml_prefere_au_nom_du_sous_cas(self, monkeypatch, journal):
        """Le `.info` doit porter le nom Intella du cas, pas celui du dossier.

        Sinon le fichier écrit par l'inventaire du compound ne serait pas celui
        relu quand l'utilisateur ouvre ce sous-cas comme cas courant.
        """
        _lines, log = journal
        monkeypatch.setattr(case_export, "run_export_source_list", fake_export(
            {"A": ["s1"]}, zero={"A": ["d1"]}, case_names={"A": "CAS RÉEL P1"}))
        _rows, _cols, inv = case_export.run_export_subcases(
            "x.exe", "u", [sub("Dossier P1", "A")], log)
        assert inv["folder_unknown"][0]["case_name"] == "CAS RÉEL P1"

    def test_repli_sur_le_nom_du_sous_cas(self, monkeypatch, journal):
        _lines, log = journal
        monkeypatch.setattr(case_export, "run_export_source_list", fake_export(
            {"A": ["s1"]}, zero={"A": ["d1"]}))
        _rows, _cols, inv = case_export.run_export_subcases(
            "x.exe", "u", [sub("Sub A", "A")], log)
        assert inv["folder_unknown"][0]["case_name"] == "Sub A"


class TestEchecsPartiels:
    def test_sous_cas_inaccessible_reporte_sans_appel(self, monkeypatch, journal):
        _lines, log = journal
        monkeypatch.setattr(case_export, "run_export_source_list",
                            fake_export({"A": ["s1"]}))
        rows, _cols, inv = case_export.run_export_subcases(
            "x.exe", "u",
            [sub("Sub A", "A"), sub("Absent", "Z", exists=False, error="hors du poste")],
            log)
        assert len(rows) == 1
        ko = [r for r in inv["subcase_reports"] if not r["ok"]]
        assert len(ko) == 1 and ko[0]["error"] == "hors du poste"

    def test_echec_intellacmd_nempeche_pas_les_autres(self, monkeypatch, journal):
        _lines, log = journal
        monkeypatch.setattr(case_export, "run_export_source_list",
                            fake_export({"A": ["s1"], "B": []}, fail={"B"}))
        rows, _cols, inv = case_export.run_export_subcases(
            "x.exe", "u", [sub("Sub A", "A"), sub("Sub B", "B")], log)
        assert len(rows) == 1
        assert [r["ok"] for r in inv["subcase_reports"]] == [True, False]
        assert "code 1" in inv["subcase_reports"][1]["error"]

    def test_rapport_par_sous_cas_lu(self, monkeypatch, journal):
        _lines, log = journal
        monkeypatch.setattr(case_export, "run_export_source_list",
                            fake_export({"A": ["s1", "s2"]}))
        _rows, _cols, inv = case_export.run_export_subcases(
            "x.exe", "u", [sub("Sub A", "A")], log)
        (rep,) = inv["subcase_reports"]
        assert rep["ok"] and rep["source_count"] == 2 and rep["bytes"] == 200

    def test_tous_en_echec_leve(self, monkeypatch, journal):
        _lines, log = journal
        monkeypatch.setattr(case_export, "run_export_source_list",
                            fake_export({"A": []}, fail={"A"}))
        with pytest.raises(RuntimeError):
            case_export.run_export_subcases("x.exe", "u", [sub("Sub A", "A")], log)

    def test_compound_sans_sous_cas_ne_leve_pas(self, journal):
        _lines, log = journal
        rows, _cols, inv = case_export.run_export_subcases("x.exe", "u", [], log)
        assert rows == [] and inv["source_count"] == 0


class TestRepliSurLeCheminDeclare:
    """Le sous-cas a deux écritures (hôte du compound / hôte déclaré au XML).

    ``case_meta.read_subcases`` met en tête celle du compound ; si IntellaCmd
    échoue dessus, on retente celle du ``case.xml`` avant de déclarer forfait —
    rien ne garantit que la bonne session SMB soit toujours la même.
    """
    def _sub(self, path, declared):
        s = sub("Sub A", path)
        s["declared_path"] = declared
        return s

    def test_repli_si_le_premier_chemin_echoue(self, monkeypatch, journal):
        lignes, log = journal
        monkeypatch.setattr(case_export.os.path, "isdir", lambda p: True)
        monkeypatch.setattr(case_export, "run_export_source_list",
                            fake_export({"NOM": [], "IP": ["s1"]}, fail={"NOM"}))
        rows, _cols, inv = case_export.run_export_subcases(
            "x.exe", "u", [self._sub("NOM", "IP")], log)

        assert len(rows) == 1
        (rep,) = inv["subcase_reports"]
        assert rep["ok"] and rep["error"] == "" and rep["path"] == "IP"
        assert any("Nouvel essai" in l for l in lignes)

    def test_pas_de_second_essai_si_le_premier_passe(self, monkeypatch, journal):
        lignes, log = journal
        monkeypatch.setattr(case_export.os.path, "isdir", lambda p: True)
        monkeypatch.setattr(case_export, "run_export_source_list",
                            fake_export({"NOM": ["s1"], "IP": ["s1"]}))
        rows, _cols, _inv = case_export.run_export_subcases(
            "x.exe", "u", [self._sub("NOM", "IP")], log)
        assert len(rows) == 1 and not any("Nouvel essai" in l for l in lignes)

    def test_chemin_declare_injoignable_pas_retente(self, monkeypatch, journal):
        lignes, log = journal
        monkeypatch.setattr(case_export.os.path, "isdir", lambda p: p != "IP")
        monkeypatch.setattr(case_export, "run_export_source_list",
                            fake_export({"NOM": []}, fail={"NOM"}))
        with pytest.raises(RuntimeError):
            case_export.run_export_subcases(
                "x.exe", "u", [self._sub("NOM", "IP")], log)
        assert not any("Nouvel essai" in l for l in lignes)


class TestDiagnosticSansXml:
    """IntellaCmd renvoie 0 même en échec : le motif se lit dans les flux.

    Le message générique « vérifiez la licence » a fait chercher au mauvais
    endroit un refus d'écriture sur un partage (07/09/2026).
    """
    TRACE_LOCK = (
        "java.nio.file.AccessDeniedException: "
        "\\\\192.0.2.174\\part\\CAS (2)\\case.xml.lock\n"
        "\tat com.vound.intella.util.LockFile.lock(LockFile.java:131)"
    )

    def test_verrou_refuse(self):
        msg = case_export.diagnose_no_xml("", self.TRACE_LOCK)
        assert "case.xml.lock" in msg and "ÉCRIRE" in msg

    def test_licence_seulement_sur_marqueur_dabsence(self):
        # « Using license: … » figure aussi dans les exports RÉUSSIS.
        assert case_export.diagnose_no_xml("Using license: Intella Node", "") == ""
        assert "licence" in case_export.diagnose_no_xml("No license found", "")

    def test_rien_de_reconnu(self):
        assert case_export.diagnose_no_xml("", "") == ""
