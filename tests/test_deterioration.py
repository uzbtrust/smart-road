"""Tests for PCI deterioration and treatment.

The published models are checked by reproducing their authors' own tables and
figures, which is the same standard the ASTM engine is held to elsewhere.
"""
from __future__ import annotations

import pytest

from smartroad.forecast.deterioration import (IRI_TO_PCI_INTERCEPT,
                                              KERALA_VALID_AGE,
                                              NO_TREATMENT_ABOVE,
                                              UZBEK_PCI_PER_YEAR,
                                              forecast_aged, forecast_linear,
                                              iri_from_pci, kerala_age_for_pci,
                                              kerala_pci, kerala_turning_age,
                                              pci_from_iri, treatment_gain,
                                              years_until)

TREATMENTS = ("shoulder_maintenance", "pothole_patching",
              "patching_slurry_seal", "resurfacing")

#: Mathew & Isaac Table 2: (age in 2009, construction quality, published PCI).
KERALA_CASE_STUDY = [
    (6.2, 0.625, 7.00), (6.0, 0.750, 15.5), (5.8, 0.750, 19.6),
    (5.5, 0.750, 27.4), (6.0, 0.625, 11.5), (5.0, 0.625, 36.5),
    (5.8, 0.750, 19.6), (5.8, 0.563, 14.6), (5.8, 0.563, 14.6),
    (4.9, 0.750, 40.5), (5.2, 0.625, 32.9), (5.0, 0.625, 36.5),
    (5.8, 0.750, 19.6), (6.0, 0.563, 10.0), (6.0, 0.625, 11.5),
]


@pytest.mark.parametrize("age,cq,published", KERALA_CASE_STUDY)
def test_reproduces_the_published_case_study(age, cq, published):
    assert kerala_pci(age, cq) == pytest.approx(published, abs=1.3)


def test_the_case_study_error_is_rounding_not_bias():
    errors = [kerala_pci(a, c) - p for a, c, p in KERALA_CASE_STUDY]
    mean_abs = sum(abs(e) for e in errors) / len(errors)
    assert mean_abs < 0.5
    assert abs(sum(errors) / len(errors)) < 0.3      # no systematic drift


def test_reproduces_figure_3_end_to_end():
    """PCI 39 at age 5, a slurry seal takes it to 74, the road is 3.2 again."""
    pci = kerala_pci(5.0, 0.75)
    assert pci == pytest.approx(39, abs=0.5)
    improved = pci + treatment_gain(pci, "patching_slurry_seal")
    assert improved == pytest.approx(74, abs=1.0)
    assert kerala_age_for_pci(improved, 0.75) == pytest.approx(3.2, abs=0.2)


def test_the_curve_falls_throughout_the_range_that_matters():
    """It reaches zero and flattens long before the turn, at every quality."""
    for cq in (0.5, 0.625, 0.75, 1.0):
        assert kerala_turning_age(cq) > KERALA_VALID_AGE[1]   # past the data
        series = [kerala_pci(a / 2, cq) for a in range(0, 14)]
        assert all(b <= a for a, b in zip(series, series[1:]))
        assert series[0] > series[-1]


def test_the_inverse_is_bounded_by_the_turning_point():
    """Searching past it walks off the far side and returns nonsense."""
    for cq in (0.5625, 0.75):
        for target in (90.0, 74.0, 40.0, 5.0):
            age = kerala_age_for_pci(target, cq)
            assert age <= kerala_turning_age(cq) + 1e-6
            assert kerala_pci(age, cq) == pytest.approx(target, abs=0.5)


def test_construction_quality_is_a_fraction():
    with pytest.raises(ValueError, match="0 to 1"):
        kerala_pci(5.0, 1.5)
    with pytest.raises(ValueError, match="negative"):
        kerala_pci(-1.0, 0.75)


# ------------------------------------------------------ roughness conversion

def test_roughness_converts_to_pci_by_the_dissertation_regression():
    # Figure 2.9 slopes run -9.4 to -10.6, intercepts 93.2 to 97.8.
    assert pci_from_iri(2.0) == pytest.approx(75.6, abs=1.0)
    assert pci_from_iri(4.0) == pytest.approx(55.2, abs=1.0)
    assert pci_from_iri(0.0) == pytest.approx(IRI_TO_PCI_INTERCEPT, abs=0.1)


def test_roughness_conversion_round_trips():
    for pci in (20.0, 51.4, 80.0):
        assert pci_from_iri(iri_from_pci(pci)) == pytest.approx(pci, abs=0.1)


def test_pci_stays_inside_its_scale():
    assert pci_from_iri(20.0) == 0.0                 # absurdly rough
    assert pci_from_iri(-5.0) == 100.0


# ------------------------------------------------------------------ treatment

def test_a_worse_road_gains_more_from_the_same_treatment():
    for t in ("pothole_patching", "patching_slurry_seal", "resurfacing"):
        assert treatment_gain(25.0, t) >= treatment_gain(65.0, t)


def test_resurfacing_buys_more_than_patching_at_every_condition():
    for pci in (15.0, 35.0, 55.0, 75.0):
        assert treatment_gain(pci, "resurfacing") > treatment_gain(pci, "pothole_patching")


def test_a_sound_pavement_is_credited_with_nothing():
    """Table 1 records no action above 80; crediting one would buy an
    optimiser a gain for money it need not spend."""
    for t in TREATMENTS:
        assert treatment_gain(NO_TREATMENT_ABOVE + 5, t) == 0.0


def test_an_unknown_treatment_is_refused():
    with pytest.raises(ValueError, match="unknown treatment"):
        treatment_gain(50.0, "wishful_thinking")


# ------------------------------------------------------------------ forecasts

def test_the_linear_forecast_follows_the_observed_uzbek_rate():
    f = forecast_linear(51.4, 10, start_year=2026)
    assert len(f) == 11
    assert f[0].pci == pytest.approx(51.4)
    assert f[10].pci == pytest.approx(51.4 + 10 * UZBEK_PCI_PER_YEAR, abs=0.01)
    assert f[0].year == 2026 and f[10].year == 2036


def test_the_forecast_carries_the_astm_band_not_just_a_number():
    f = forecast_linear(51.4, 10)
    assert f[0].rating == "Poor"
    assert f[-1].rating == "Very Poor"


def test_a_forecast_cannot_fall_below_zero():
    assert forecast_linear(3.0, 20)[-1].pci == 0.0


def test_years_until_a_threshold():
    assert years_until(51.4, 40.0) == pytest.approx(5.56, abs=0.05)
    assert years_until(51.4, 55.0) is None           # already below it
    assert years_until(51.4, 40.0, per_year=0.0) is None


def test_treating_resets_the_age_and_the_road_climbs():
    untreated = forecast_aged(5.0, 0.75, 6)
    treated = forecast_aged(5.0, 0.75, 6, treat_at=40.0)
    assert treated[-1].pci > untreated[-1].pci
    fired = [p for p in treated if p.treatment]
    assert fired and fired[0].gain > 0
    # The reset age is younger than the year before it.
    i = treated.index(fired[0])
    assert treated[i].age_years < treated[i - 1].age_years
