"""Tests for the ASTM D6433 PCI engine.

The anchor is the worked example printed in ASTM D6433-07: the flexible-pavement
data sheet in Fig. 4 and its calculation in Fig. 6. If that reproduces, the curve
data, the m formula, the fractional-deduct rule and the CDV iteration are all
behaving as the standard describes.
"""
import math

import pytest

from smartroad.pci.engine import (
    Distress,
    SampleUnit,
    allowable_deduct_count,
    corrected_deduct_value,
    deduct_value,
    rate,
    section_pci,
)

# ASTM D6433-07 Fig. 4 -- Springfield, section 001, sample unit 1, 2500 sq ft.
# Quantities are summed per (type, severity) exactly as the data sheet records them.
ASTM_FIG4 = [
    Distress("alligator_cracking", "low", 5),
    Distress("alligator_cracking", "low", 4),
    Distress("alligator_cracking", "low", 4),
    Distress("alligator_cracking", "high", 8),
    Distress("alligator_cracking", "high", 6),
    Distress("edge_cracking", "low", 32),
    Distress("edge_cracking", "low", 15),
    Distress("edge_cracking", "low", 18),
    Distress("edge_cracking", "low", 24),
    Distress("edge_cracking", "low", 41),
    Distress("joint_reflection_cracking", "medium", 20),
    Distress("joint_reflection_cracking", "medium", 15),
    Distress("joint_reflection_cracking", "medium", 35),
    Distress("joint_reflection_cracking", "medium", 27),
    Distress("joint_reflection_cracking", "medium", 23),
    Distress("joint_reflection_cracking", "medium", 10),
    Distress("joint_reflection_cracking", "medium", 13),
    Distress("patching_and_utility_cut_patching", "high", 12),
    Distress("patching_and_utility_cut_patching", "high", 10),
    Distress("potholes", "low", 1),
    Distress("rutting", "low", 4),
    Distress("rutting", "low", 9),
    Distress("rutting", "low", 8),
    Distress("weathering", "low", 250),
]


@pytest.fixture
def fig4():
    return SampleUnit(area=2500, distresses=ASTM_FIG4, units="imperial",
                      identifier="B9").evaluate()


class TestAstmWorkedExample:
    """ASTM D6433-07 Fig. 4 -> Fig. 6."""

    def test_densities_match_data_sheet(self):
        d = SampleUnit(area=2500, distresses=ASTM_FIG4, units="imperial").densities()
        # Fig. 4 "DENSITY %" column.
        assert d[("alligator_cracking", "low")] == pytest.approx(0.52, abs=0.01)
        assert d[("alligator_cracking", "high")] == pytest.approx(0.56, abs=0.01)
        assert d[("edge_cracking", "low")] == pytest.approx(5.20, abs=0.01)
        assert d[("joint_reflection_cracking", "medium")] == pytest.approx(5.72, abs=0.01)
        assert d[("patching_and_utility_cut_patching", "high")] == pytest.approx(0.88, abs=0.01)
        assert d[("potholes", "low")] == pytest.approx(0.04, abs=0.01)
        assert d[("rutting", "low")] == pytest.approx(0.84, abs=0.01)
        assert d[("weathering", "low")] == pytest.approx(10.0, abs=0.01)

    def test_highest_deduct_value(self, fig4):
        # Fig. 6 header: HDV = 25.1
        assert fig4.highest_deduct == pytest.approx(25.1, abs=0.5)

    def test_allowable_number_of_deducts(self, fig4):
        # Fig. 6: m = 1 + (9/98)(100 - 25.1) = 7.9
        assert fig4.allowable_deducts == pytest.approx(7.9, abs=0.05)

    def test_max_corrected_deduct_value(self, fig4):
        # Fig. 6: max CDV = 51
        assert fig4.max_cdv == pytest.approx(51.0, abs=1.0)

    def test_pci(self, fig4):
        # Fig. 6: PCI = 100 - 51 = 49
        assert fig4.pci == pytest.approx(49.0, abs=1.0)

    def test_rating(self, fig4):
        # Fig. 1 puts 40-55 in "Poor". (The Fig. 6 worksheet is hand-annotated
        # "FAIR", which contradicts the standard's own rating scale.)
        assert fig4.rating == "Poor"

    def test_iteration_q_descends_to_one(self, fig4):
        qs = [it["q"] for it in fig4.iterations]
        assert qs == sorted(qs, reverse=True)
        assert qs[-1] == 1
        # Fig. 6 tabulates eight rows, q = 8 down to 1.
        assert qs[0] == 8


class TestRatingScale:
    @pytest.mark.parametrize(
        "pci,expected",
        [
            (100, "Good"), (85, "Good"), (84.9, "Satisfactory"),
            (70, "Satisfactory"), (69.9, "Fair"), (55, "Fair"),
            (54.9, "Poor"), (40, "Poor"), (39.9, "Very Poor"),
            (25, "Very Poor"), (24.9, "Serious"), (10, "Serious"),
            (9.9, "Failed"), (0, "Failed"),
        ],
    )
    def test_boundaries(self, pci, expected):
        assert rate(pci)[0] == expected

    @pytest.mark.parametrize("bad", [-0.1, 100.1])
    def test_out_of_range_rejected(self, bad):
        with pytest.raises(ValueError):
            rate(bad)


class TestDeductValue:
    def test_zero_density_is_zero_deduct(self):
        assert deduct_value("alligator_cracking", "low", 0.0) == 0.0

    def test_monotonic_in_density(self):
        prev = -1.0
        for density in (0.5, 1, 2, 5, 10, 20, 50):
            dv = deduct_value("alligator_cracking", "low", density)
            assert dv >= prev, f"deduct fell at density {density}"
            prev = dv

    def test_severity_ordering(self):
        # At a fixed density a worse severity must never deduct less.
        for density in (1, 5, 10, 25):
            low = deduct_value("alligator_cracking", "low", density)
            med = deduct_value("alligator_cracking", "medium", density)
            high = deduct_value("alligator_cracking", "high", density)
            assert low <= med <= high, f"severity order broken at {density}%"

    def test_clamped_to_chart_range(self):
        # Beyond the digitised extent the value must plateau, not extrapolate.
        assert deduct_value("potholes", "high", 1000) == deduct_value("potholes", "high", 100)

    def test_bounded_0_100(self):
        for distress in ("alligator_cracking", "potholes", "rutting", "weathering"):
            for sev in ("low", "medium", "high"):
                for density in (0.01, 0.1, 1, 10, 100):
                    assert 0.0 <= deduct_value(distress, sev, density) <= 100.0

    def test_unknown_distress_rejected(self):
        with pytest.raises(KeyError, match="unknown asphalt distress"):
            deduct_value("banana_cracking", "low", 5)

    def test_negative_density_rejected(self):
        with pytest.raises(ValueError):
            deduct_value("alligator_cracking", "low", -1)


class TestCorrectedDeductValue:
    def test_q1_is_near_identity(self):
        # With a single deduct above 2 the correction curve is essentially y = x.
        for total in (10, 40, 80):
            assert corrected_deduct_value(total, 1) == pytest.approx(total, abs=0.5)

    def test_more_deducts_correct_downwards(self):
        # Spreading the same total over more distress types must not raise the CDV.
        total = 100.0
        values = [corrected_deduct_value(total, q) for q in range(1, 11)]
        assert values[0] == max(values)

    def test_q_out_of_range_rejected(self):
        for bad in (0, 11):
            with pytest.raises(ValueError):
                corrected_deduct_value(50, bad)


class TestAllowableDeductCount:
    def test_formula(self):
        assert allowable_deduct_count(25.1) == pytest.approx(7.9, abs=0.05)
        assert allowable_deduct_count(100.0) == pytest.approx(1.0, abs=0.01)

    def test_capped_at_ten(self):
        assert allowable_deduct_count(0.0) == 10.0


class TestSampleUnit:
    def test_pristine_unit_scores_100(self):
        r = SampleUnit(area=225, distresses=[]).evaluate()
        assert r.pci == 100.0
        assert r.rating == "Good"

    def test_repeats_are_summed_before_density(self):
        """Five 4 m2 patches must deduct the same as one 20 m2 patch."""
        many = SampleUnit(area=225, distresses=[Distress("alligator_cracking", "low", 4)] * 5)
        one = SampleUnit(area=225, distresses=[Distress("alligator_cracking", "low", 20)])
        assert many.evaluate().pci == pytest.approx(one.evaluate().pci)

    def test_worse_pavement_scores_lower(self):
        light = SampleUnit(area=225, distresses=[Distress("alligator_cracking", "low", 5)])
        heavy = SampleUnit(area=225, distresses=[Distress("alligator_cracking", "high", 80)])
        assert heavy.evaluate().pci < light.evaluate().pci

    def test_adding_distress_never_raises_pci(self):
        base = [Distress("longitudinal_transverse_cracking", "medium", 30)]
        extra = base + [Distress("potholes", "high", 3)]
        assert SampleUnit(area=225, distresses=extra).evaluate().pci <= (
            SampleUnit(area=225, distresses=base).evaluate().pci
        )

    def test_pci_stays_in_range_under_extreme_input(self):
        r = SampleUnit(
            area=225,
            distresses=[Distress(t, "high", 225) for t in
                        ("alligator_cracking", "block_cracking", "potholes",
                         "rutting", "weathering", "shoving", "depression")],
        ).evaluate()
        assert 0.0 <= r.pci <= 100.0

    def test_single_small_deduct_bypasses_cdv_curve(self):
        """ASTM 9.5.1: with no deduct above 2, the total is used directly."""
        r = SampleUnit(area=2500, distresses=[Distress("potholes", "low", 0.5)]).evaluate()
        assert r.q == 0
        assert r.max_cdv == pytest.approx(sum(r.deduct_values))

    def test_invalid_area_rejected(self):
        for bad in (0, -5):
            with pytest.raises(ValueError):
                SampleUnit(area=bad)

    def test_negative_quantity_rejected(self):
        with pytest.raises(ValueError):
            Distress("potholes", "low", -1)


class TestSectionPci:
    def test_area_weighted(self):
        a = SampleUnit(area=100, distresses=[])
        b = SampleUnit(area=300, distresses=[Distress("alligator_cracking", "high", 150)])
        ra, rb = a.evaluate(), b.evaluate()
        expected = (ra.pci * 100 + rb.pci * 300) / 400
        assert section_pci([a, b]) == pytest.approx(expected)

    def test_empty_section_rejected(self):
        with pytest.raises(ValueError):
            section_pci([])
