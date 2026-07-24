"""Deterministic ROI model.

No LLM touches any arithmetic in this module. Agents supply the *assumptions*
— volumes, touch times, what share of a process is automatable — and this code
turns them into a number the same way every time.

That split is the whole point. A business case whose figures came out of a
language model cannot be audited, cannot be reproduced, and will not survive
its first serious question from a finance director. Here, every input is
explicit and every intermediate is exposed, so an argument about the result is
an argument about a named assumption.
"""

from __future__ import annotations

from dataclasses import dataclass

from automotive_ops_intelligence.models import (
    AutomationDesign,
    CostBasis,
    CostBreakdown,
    ProcessProfile,
    ROIResult,
    SensitivityBand,
)

MONTHS_PER_YEAR = 12
MINUTES_PER_HOUR = 60


def compute_roi(process: ProcessProfile, design: AutomationDesign) -> ROIResult:
    """Return the annual cost impact of applying `design` to `process`.

    The model is intentionally simple: labour plus error cost before, labour
    plus error plus run cost after. It does not attempt to price revenue upside,
    working-capital effects, or customer-satisfaction gains — those are real but
    unfalsifiable at proposal stage, and including them is how automation
    business cases lose their credibility.
    """
    # Effective share is the product, not the minimum. A system that can handle
    # 80% of volume but is only trusted with 60% of eligible cases touches 48%.
    effective_share = design.automatable_share * design.adoption_rate
    automated_units = process.annual_volume * effective_share
    manual_units = process.annual_volume - automated_units

    baseline = CostBreakdown(
        labour_cost=_labour_cost(
            units=process.annual_volume,
            minutes_per_unit=process.minutes_per_unit_manual,
            hourly_cost=process.fully_loaded_hourly_cost,
        ),
        error_cost=process.annual_volume * process.error_rate * process.cost_per_error,
    )

    projected = CostBreakdown(
        labour_cost=(
            _labour_cost(
                units=manual_units,
                minutes_per_unit=process.minutes_per_unit_manual,
                hourly_cost=process.fully_loaded_hourly_cost,
            )
            # The automated path is not free of humans. Someone still reviews
            # exceptions and approves anything above threshold.
            + _labour_cost(
                units=automated_units,
                minutes_per_unit=design.minutes_per_unit_assisted,
                hourly_cost=process.fully_loaded_hourly_cost,
            )
        ),
        error_cost=(
            manual_units * process.error_rate * process.cost_per_error
            + automated_units * design.residual_error_rate * process.cost_per_error
        ),
        run_cost=(
            design.annual_platform_cost + automated_units * design.cost_per_unit_inference
        ),
    )

    gross_annual_saving = baseline.total - projected.total

    # Split the saving by what it actually is. Labour released and run cost are
    # always cash. Error savings are cash or foregone margin depending on the
    # process, and the two do not deserve equal weight in a funding decision.
    error_saving = baseline.error_cost - projected.error_cost
    labour_and_run = (baseline.labour_cost - projected.labour_cost) - projected.run_cost

    if process.error_cost_basis is CostBasis.CASH:
        cash_saving = labour_and_run + error_saving
        opportunity_saving = 0.0
    else:
        cash_saving = labour_and_run
        opportunity_saving = error_saving

    year_one_net = gross_annual_saving - design.build_cost

    # Payback is computed on cash only. Funding a build out of margin you hope
    # to capture is how these projects get cancelled in month nine.
    payback_months: float | None = None
    if cash_saving > 0:
        payback_months = design.build_cost / (cash_saving / MONTHS_PER_YEAR)

    hours_released = (
        process.annual_volume * process.minutes_per_unit_manual
        - (
            manual_units * process.minutes_per_unit_manual
            + automated_units * design.minutes_per_unit_assisted
        )
    ) / MINUTES_PER_HOUR

    return ROIResult(
        currency=process.currency,
        baseline=baseline,
        projected=projected,
        automated_units=automated_units,
        manual_units=manual_units,
        gross_annual_saving=gross_annual_saving,
        cash_saving=cash_saving,
        opportunity_saving=opportunity_saving,
        year_one_net=year_one_net,
        payback_months=payback_months,
        hours_released_per_year=hours_released,
    )


def _labour_cost(*, units: float, minutes_per_unit: float, hourly_cost: float) -> float:
    return units * (minutes_per_unit / MINUTES_PER_HOUR) * hourly_cost


@dataclass(frozen=True)
class SensitivityConfig:
    """How far to flex the two assumptions the model is most sensitive to.

    Automatable share and adoption rate are the soft numbers — they are
    judgment, not measurement — and they multiply together, so error in them
    compounds. Build cost is flexed upward only, because implementation
    estimates are reliably optimistic and rarely wrong in the cheap direction.
    """

    share_delta: float = 0.20
    adoption_delta: float = 0.20
    pessimistic_build_multiplier: float = 1.5


def compute_sensitivity(
    process: ProcessProfile,
    design: AutomationDesign,
    config: SensitivityConfig | None = None,
) -> SensitivityBand:
    """Return the base case flanked by an unkind and a generous scenario.

    A single-point ROI figure invites false precision. A band invites the right
    conversation: does this still make sense at the bottom of the range?
    """
    cfg = config or SensitivityConfig()

    pessimistic = design.model_copy(
        update={
            "automatable_share": _clamp(design.automatable_share * (1 - cfg.share_delta)),
            "adoption_rate": _clamp(design.adoption_rate * (1 - cfg.adoption_delta)),
            "build_cost": design.build_cost * cfg.pessimistic_build_multiplier,
        }
    )
    optimistic = design.model_copy(
        update={
            "automatable_share": _clamp(design.automatable_share * (1 + cfg.share_delta)),
            "adoption_rate": _clamp(design.adoption_rate * (1 + cfg.adoption_delta)),
        }
    )

    return SensitivityBand(
        pessimistic=compute_roi(process, pessimistic),
        base=compute_roi(process, design),
        optimistic=compute_roi(process, optimistic),
    )


def _clamp(value: float, low: float = 0.0, high: float = 1.0) -> float:
    return max(low, min(high, value))
