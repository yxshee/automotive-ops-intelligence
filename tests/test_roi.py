"""Tests for the deterministic ROI model.

These pin arithmetic, not behaviour. The point of computing return in plain
Python rather than asking a model for it is that the result is checkable, so it
should be checked.
"""

from __future__ import annotations

import pytest

from automotive_ops_intelligence.models import (
    AutomationDesign,
    CostBasis,
    ProcessProfile,
)
from automotive_ops_intelligence.roi import (
    SensitivityConfig,
    compute_roi,
    compute_sensitivity,
)


def make_process(**overrides) -> ProcessProfile:
    defaults = dict(
        name="test process",
        description="",
        annual_volume=1000,
        minutes_per_unit_manual=60.0,
        fully_loaded_hourly_cost=100.0,
        error_rate=0.10,
        cost_per_error=1000.0,
        error_cost_basis=CostBasis.CASH,
    )
    return ProcessProfile(**{**defaults, **overrides})


def make_design(**overrides) -> AutomationDesign:
    defaults = dict(
        approach="",
        automatable_share=0.5,
        adoption_rate=1.0,
        minutes_per_unit_assisted=0.0,
        residual_error_rate=0.0,
        build_cost=0.0,
        annual_platform_cost=0.0,
        cost_per_unit_inference=0.0,
        human_in_the_loop="",
    )
    return AutomationDesign(**{**defaults, **overrides})


def test_baseline_is_labour_plus_error_cost():
    # 1000 units x 1 hour x 100/hr = 100_000 labour
    # 1000 units x 10% x 1000     = 100_000 error
    result = compute_roi(make_process(), make_design())
    assert result.baseline.labour_cost == pytest.approx(100_000)
    assert result.baseline.error_cost == pytest.approx(100_000)
    assert result.baseline.total == pytest.approx(200_000)


def test_effective_share_is_the_product_of_capability_and_adoption():
    """A system handling 80% of volume, trusted with 50% of cases, touches 40%."""
    result = compute_roi(
        make_process(),
        make_design(automatable_share=0.8, adoption_rate=0.5),
    )
    assert result.automated_units == pytest.approx(400)
    assert result.manual_units == pytest.approx(600)


def test_perfect_automation_of_half_the_volume_halves_cost():
    result = compute_roi(make_process(), make_design())
    assert result.projected.total == pytest.approx(100_000)
    assert result.gross_annual_saving == pytest.approx(100_000)
    assert result.hours_released_per_year == pytest.approx(500)


def test_residual_review_time_is_charged():
    """The automated path still costs human time; it is not free."""
    with_review = compute_roi(make_process(), make_design(minutes_per_unit_assisted=30.0))
    without_review = compute_roi(make_process(), make_design())
    assert with_review.projected.labour_cost > without_review.projected.labour_cost
    # 500 automated units x 0.5h x 100/hr = 25_000 of residual review
    assert with_review.projected.labour_cost == pytest.approx(75_000)


def test_run_cost_reduces_the_saving():
    result = compute_roi(
        make_process(),
        make_design(annual_platform_cost=10_000, cost_per_unit_inference=2.0),
    )
    # 10_000 platform + 500 automated x 2.0 = 11_000
    assert result.projected.run_cost == pytest.approx(11_000)
    assert result.gross_annual_saving == pytest.approx(89_000)


def test_payback_is_computed_on_cash_only():
    """Funding a build out of hoped-for margin is how projects get cancelled."""
    result = compute_roi(
        make_process(error_cost_basis=CostBasis.OPPORTUNITY),
        make_design(build_cost=120_000),
    )
    # Labour saving is cash (50_000); the error saving is opportunity (50_000).
    assert result.cash_saving == pytest.approx(50_000)
    assert result.opportunity_saving == pytest.approx(50_000)
    assert result.gross_annual_saving == pytest.approx(100_000)
    # Payback uses the 50_000 cash figure, not the 100_000 total.
    assert result.payback_months == pytest.approx(28.8)


def test_cash_basis_puts_the_whole_saving_in_cash():
    result = compute_roi(make_process(error_cost_basis=CostBasis.CASH), make_design())
    assert result.opportunity_saving == pytest.approx(0)
    assert result.cash_saving == pytest.approx(result.gross_annual_saving)


def test_no_payback_when_there_is_no_cash_saving():
    """A design that costs more to run than it saves must not report a payback."""
    result = compute_roi(
        make_process(),
        make_design(annual_platform_cost=500_000, build_cost=10_000),
    )
    assert result.gross_annual_saving < 0
    assert result.payback_months is None
    assert result.pays_back() is False


def test_year_one_net_carries_the_build_cost():
    result = compute_roi(make_process(), make_design(build_cost=250_000))
    assert result.gross_annual_saving == pytest.approx(100_000)
    assert result.year_one_net == pytest.approx(-150_000)


def test_sensitivity_band_is_ordered():
    band = compute_sensitivity(make_process(), make_design(build_cost=50_000))
    assert (
        band.pessimistic.gross_annual_saving
        < band.base.gross_annual_saving
        < band.optimistic.gross_annual_saving
    )


def test_pessimistic_case_also_inflates_the_build_cost():
    """Implementation estimates are reliably optimistic, never the reverse."""
    config = SensitivityConfig(pessimistic_build_multiplier=2.0)
    band = compute_sensitivity(make_process(), make_design(build_cost=100_000), config)
    # Year-one net absorbs the doubled build cost.
    assert band.pessimistic.year_one_net < band.base.year_one_net - 100_000


def test_shares_are_clamped_to_valid_range():
    """An optimistic flex must not push a 95% share above 100%."""
    band = compute_sensitivity(
        make_process(),
        make_design(automatable_share=0.95, adoption_rate=0.95),
    )
    assert band.optimistic.automated_units <= 1000
