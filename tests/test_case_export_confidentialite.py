"""XML temporaires et journalisation des flux IntellaCmd.

Deux contrats posés par l'audit paranoid du 18/09/2026 :

- ``sources.xml`` (chemins des pièces, scellés, tâches) ne survit pas au relevé
  suivant, et un dossier abandonné par une session antérieure finit par être
  purgé ;
- le journal applicatif, qui s'affiche et s'exporte, ne reçoit plus ni
  ``-log DEBUG`` ni l'intégralité des flux d'IntellaCmd.

IntellaCmd n'est jamais lancé : ``subprocess.run`` est remplacé par un faux qui
écrit le XML attendu.
"""

import os
import time

import case_export


CASE_XML = """<?xml version="1.0" encoding="UTF-8"?>
<sources><caseName>Cas</caseName>
<source><name>s1</name><type>File or Folder</type><size>10</size>
<path>D:\\s1</path></source></sources>
"""


class _Proc:
    returncode = 0

    def __init__(self, stdout="", stderr=""):
        self.stdout, self.stderr = stdout, stderr


def _faux_intellacmd(monkeypatch, stdout="", stderr=""):
    """Remplace ``subprocess.run`` : écrit le XML demandé et rend les flux voulus."""
    vus = []

    def _run(cmd, **kwargs):
        vus.append(list(cmd))
        with open(cmd[cmd.index("-exportSourceList") + 1], "w",
                  encoding="utf-8") as f:
            f.write(CASE_XML)
        return _Proc(stdout, stderr)

    monkeypatch.setattr(case_export.subprocess, "run", _run)
    monkeypatch.setattr(os.path, "isfile",
                        lambda p: True if p.endswith(".exe") else os.path.exists(p))
    return vus


def _journal():
    lignes = []
    return lignes, lignes.append


class TestXmlTemporaires:
    def test_le_releve_suivant_purge_le_precedent(self, monkeypatch):
        _faux_intellacmd(monkeypatch)
        _l, log = _journal()
        *_, inv1 = case_export.run_export_source_list("i.exe", "u", "D:\\Cas", log)
        premier = inv1["xml_path"]
        assert os.path.isfile(premier)

        *_, inv2 = case_export.run_export_source_list("i.exe", "u", "D:\\Cas", log)
        # Le XML du relevé précédent a disparu ; celui du relevé courant vit
        # (« Info Profil » et « Exporter le XML » le relisent).
        assert not os.path.exists(premier)
        assert os.path.isfile(inv2["xml_path"])
        case_export.start_export_batch()

    def test_un_compound_ne_purge_pas_ses_propres_sous_cas(self, monkeypatch):
        _faux_intellacmd(monkeypatch)
        _l, log = _journal()
        case_export.start_export_batch()
        *_, a = case_export.run_export_source_list("i.exe", "u", "A", log,
                                                   new_batch=False)
        *_, b = case_export.run_export_source_list("i.exe", "u", "B", log,
                                                   new_batch=False)
        assert os.path.isfile(a["xml_path"]) and os.path.isfile(b["xml_path"])
        case_export.start_export_batch()

    def test_dossier_abandonne_purge_au_dela_de_l_age(self, tmp_path, monkeypatch):
        monkeypatch.setattr(case_export.tempfile, "gettempdir", lambda: str(tmp_path))
        vieux = tmp_path / (case_export.TEMP_PREFIX + "vieux")
        recent = tmp_path / (case_export.TEMP_PREFIX + "recent")
        etranger = tmp_path / "autre_outil"
        for d in (vieux, recent, etranger):
            d.mkdir()
        vieil_age = time.time() - (case_export.ORPHAN_MAX_AGE_H + 1) * 3600
        os.utime(vieux, (vieil_age, vieil_age))

        assert case_export.purge_orphan_exports() == 1
        assert not vieux.exists()
        # Un dossier récent peut appartenir à une AUTRE instance en cours.
        assert recent.exists() and etranger.exists()


class TestJournalDesFlux:
    def test_pas_de_log_debug_par_defaut(self, monkeypatch):
        vus = _faux_intellacmd(monkeypatch)
        _l, log = _journal()
        case_export.run_export_source_list("i.exe", "u", "D:\\Cas", log)
        cmd = vus[0]
        assert cmd[cmd.index("-log") + 1] == case_export.DEFAULT_LOG_LEVEL != "DEBUG"
        case_export.start_export_batch()

    def test_debug_explicite_retablit_le_niveau(self, monkeypatch):
        vus = _faux_intellacmd(monkeypatch)
        _l, log = _journal()
        case_export.run_export_source_list("i.exe", "u", "D:\\Cas", log, debug=True)
        cmd = vus[0]
        assert cmd[cmd.index("-log") + 1] == "DEBUG"
        case_export.start_export_batch()

    def test_flux_long_tronque_dans_le_journal(self, monkeypatch):
        flux = "\n".join(f"D:\\Scelles\\piece_{i}.pst" for i in range(200))
        _faux_intellacmd(monkeypatch, stdout=flux)
        lignes, log = _journal()
        case_export.run_export_source_list("i.exe", "u", "D:\\Cas", log)
        blob = "\n".join(lignes)
        assert "piece_0.pst" in blob
        assert "piece_199.pst" not in blob
        assert "non journalisée(s)" in blob
        case_export.start_export_batch()

    def test_mode_diagnostic_journalise_tout(self, monkeypatch):
        flux = "\n".join(f"ligne {i}" for i in range(200))
        _faux_intellacmd(monkeypatch, stdout=flux)
        lignes, log = _journal()
        case_export.run_export_source_list("i.exe", "u", "D:\\Cas", log, debug=True)
        assert "ligne 199" in "\n".join(lignes)
        case_export.start_export_batch()

    def test_le_diagnostic_voit_le_flux_entier(self, monkeypatch):
        """Le journal est bridé, pas l'analyse : le motif d'échec reste trouvé."""
        queue = "\n".join(f"bruit {i}" for i in range(100))
        assert "verrou" in case_export.diagnose_no_xml(
            queue + "\nAccessDeniedException: D:\\Cas\\case.xml.lock", "")
