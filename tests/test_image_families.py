"""Table unique des familles d'images forensiques.

Ce module est né d'une divergence qui a coûté cher : trois copies de la même
connaissance métier, dont celle de ``sizing`` ne connaissait que 3 familles sur
7 — une image LEF, SMART ou EWF v2 n'était alors comptée que sur son **premier
segment**, le volume du cas était sous-évalué et le garde-fou des 950 Go pouvait
laisser passer un cas qui le dépasse.

Il n'était éprouvé qu'**en creux**, par les suites de ses trois consommateurs
(``sizing``, ``forensic_scan``, ``path_parser``) : une régression dans une
famille qu'aucun d'eux n'exerce serait passée (audit rigorous du 18/09/2026).
Ces tests l'attaquent donc directement, famille par famille.
"""

import image_families as fam


# (libellé, 1er segment, segments suivants qui doivent être reconnus)
FAMILLES = [
    ("EWF", ".e01", [".e02", ".e99", ".eaa", ".ezz"]),
    ("EWF v2", ".ex01", [".ex02", ".ex99"]),
    ("LEF", ".l01", [".l02", ".l99"]),
    ("LEF x", ".lx01", [".lx02"]),
    ("SMART", ".s01", [".s02"]),
    ("AD1", ".ad1", [".ad2", ".ad28"]),
    ("brut découpé", ".001", [".002", ".999"]),
]


class TestPremierSegment:
    def test_chaque_famille_se_ramene_a_son_premier_segment(self):
        for libelle, premier, suivants in FAMILLES:
            assert fam.first_segment_ext(premier) == premier, libelle
            for ext in suivants:
                assert fam.first_segment_ext(ext) == premier, f"{libelle} {ext}"

    def test_au_dela_de_e99_la_numerotation_passe_aux_lettres(self):
        """Piège EWF : une même image relève de DEUX motifs (.E02 puis .EAA)."""
        assert fam.first_segment_ext(".eaa") == ".e01"
        assert len(fam.segment_patterns(".e01")) == 2

    def test_insensible_a_la_casse(self):
        # Un chemin collé en majuscules décrit la même image (défaut du 18/09).
        for ext in (".E01", ".Ex02", ".AD1", ".L01"):
            assert fam.is_segment_ext(ext), ext
        assert fam.first_segment_ext(".E02") == ".e01"

    def test_extension_inconnue_ou_vide(self):
        for ext in ("", None, ".txt", ".pst", ".e1", ".e001", ".ad", ".0001"):
            assert fam.first_segment_ext(ext) == ""
            assert fam.segment_patterns(ext) == ()
            assert fam.is_segment_ext(ext) is False


class TestMotifsDeSegments:
    def test_les_motifs_couvrent_tous_les_segments_de_leur_famille(self):
        for libelle, premier, suivants in FAMILLES:
            motifs = fam.segment_patterns(premier)
            assert motifs, libelle
            for ext in [premier] + suivants:
                assert any(m.match(ext) for m in motifs), f"{libelle} {ext}"

    def test_les_motifs_ne_debordent_pas_sur_une_autre_famille(self):
        """`.e01` ne doit pas ramasser `.ex01` : ce serait deux images fondues."""
        assert not any(m.match(".ex01") for m in fam.segment_patterns(".e01"))
        assert not any(m.match(".lx01") for m in fam.segment_patterns(".l01"))

    def test_un_segment_se_retrouve_par_n_importe_lequel_de_ses_freres(self):
        # La collecte part parfois d'un segment quelconque trouvé sur le disque.
        assert fam.segment_patterns(".e02") == fam.segment_patterns(".e01")
        assert fam.segment_patterns(".eaa") == fam.segment_patterns(".e01")


class TestSegmentNonInitial:
    def test_le_premier_segment_n_en_est_pas_un(self):
        for _libelle, premier, _suivants in FAMILLES:
            assert fam.is_non_first_segment_ext(premier) is False

    def test_les_suivants_en_sont(self):
        for libelle, _premier, suivants in FAMILLES:
            for ext in suivants:
                assert fam.is_non_first_segment_ext(ext) is True, f"{libelle} {ext}"

    def test_une_extension_inconnue_n_est_pas_un_segment_non_initial(self):
        # Sinon l'avertissement « pointez le 1er segment » crierait à tort.
        for ext in ("", ".txt", ".vmdk", ".dd"):
            assert fam.is_non_first_segment_ext(ext) is False


class TestImagesMonoFichier:
    def test_une_image_mono_fichier_n_a_pas_de_segment(self):
        """`SINGLE` = une image, un fichier : aucun motif de segment à chercher."""
        for ext in fam.SINGLE:
            assert fam.is_segment_ext(ext) is False, ext
            assert fam.segment_patterns(ext) == ()

    def test_le_catalogue_mono_fichier_est_celui_attendu(self):
        # ⚠ Élargir cette liste, c'est accepter à l'import une source qui n'est
        # peut-être pas une image — et Intella ne permet pas de revoir les
        # réglages après coup (contrat « ne jamais élargir au cas où »).
        assert fam.SINGLE == {".dd", ".vhd", ".vhdx", ".vmdk"}
