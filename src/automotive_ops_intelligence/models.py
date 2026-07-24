"""Typed contracts for every boundary in the pipeline.

Agents return these models rather than prose. A malformed agent response fails
at validation with a readable error instead of silently producing a brief with
a missing number in it.
"""

from __future__ import annotations

from enum import Enum

from pydantic import BaseModel, Field


class Confidence(str, Enum):
    """How well-grounded a claim is.

    Deliberately coarse. A model asked for a percentage confidence will happily
    produce 73% and mean nothing by it.
    """

    SOURCED = "sourced"
    """Traceable to a cited public source."""

    INFERRED = "inferred"
    """A reasonable deduction from sourced facts, but not stated anywhere."""

    ASSUMED = "assumed"
    """An input we chose. Must be varied in sensitivity analysis."""


class CostBasis(str, Enum):
    """Whether a cost is money leaving the business or money never earned.

    This distinction decides how much weight a saving deserves. Cash cost
    avoided shows up in the P&L. Opportunity cost recovered depends on a
    conversion assumption stacked on top of everything else, and a finance
    director will discount it — correctly. Reporting both under one heading is
    the most common way an automation business case overstates itself.
    """

    CASH = "cash"
    """Money actually paid out today: demurrage, rework, penalties, write-offs."""

    OPPORTUNITY = "opportunity"
    """Margin not captured: a lost lead, a mispriced unit, an idle asset."""


class Evidence(BaseModel):
    """A single factual claim with its provenance."""

    claim: str
    source_url: str | None = None
    confidence: Confidence

    def is_citable(self) -> bool:
        return self.confidence is Confidence.SOURCED and bool(self.source_url)


class ProcessProfile(BaseModel):
    """The current, pre-automation cost shape of one business process.

    All costs are per-unit and in a single currency (see `currency`). Volumes
    are annual.
    """

    name: str
    description: str
    currency: str = "AED"

    annual_volume: int = Field(gt=0, description="Units processed per year.")
    minutes_per_unit_manual: float = Field(gt=0, description="Human touch time per unit today.")
    fully_loaded_hourly_cost: float = Field(
        gt=0, description="Salary + benefits + overhead, per hour."
    )
    error_rate: float = Field(
        ge=0, le=1, description="Fraction of units that carry a defect today."
    )
    cost_per_error: float = Field(
        ge=0, description="Rework, penalty, demurrage or write-off per defect."
    )
    error_cost_basis: CostBasis = Field(
        default=CostBasis.CASH,
        description="Whether cost_per_error is cash paid out or margin foregone.",
    )

    evidence: list[Evidence] = Field(default_factory=list)


class AutomationDesign(BaseModel):
    """What the proposed system would actually change.

    `adoption_rate` is separate from `automatable_share` on purpose. The share a
    system *could* handle and the share an organisation *lets* it handle are
    different numbers, and conflating them is the most common way an automation
    business case overstates its return.
    """

    approach: str
    automatable_share: float = Field(
        ge=0, le=1, description="Fraction of volume the system can handle end-to-end."
    )
    adoption_rate: float = Field(
        ge=0, le=1, description="Fraction of eligible volume actually routed to it."
    )
    minutes_per_unit_assisted: float = Field(
        ge=0, description="Residual human review time on the automated path."
    )
    residual_error_rate: float = Field(
        ge=0, le=1, description="Defect rate on the automated path."
    )

    build_cost: float = Field(ge=0, description="One-time implementation cost.")
    annual_platform_cost: float = Field(ge=0, description="Licences, hosting, support.")
    cost_per_unit_inference: float = Field(
        ge=0, description="Model and API cost per automated unit."
    )

    human_in_the_loop: str = Field(
        description="What a human must still approve, and at what threshold."
    )


class CostBreakdown(BaseModel):
    """Every intermediate in the ROI calculation, exposed for audit.

    Nothing here is rounded until presentation. If a reviewer disputes the
    result they can dispute a specific line rather than the whole number.
    """

    labour_cost: float
    error_cost: float
    run_cost: float = 0.0

    @property
    def total(self) -> float:
        return self.labour_cost + self.error_cost + self.run_cost


class ROIResult(BaseModel):
    """Output of the deterministic ROI model. No model call produced any of this."""

    currency: str

    baseline: CostBreakdown
    projected: CostBreakdown

    automated_units: float
    manual_units: float

    gross_annual_saving: float
    cash_saving: float = Field(
        default=0.0, description="Saving that lands in the P&L: labour and cash costs avoided."
    )
    opportunity_saving: float = Field(
        default=0.0, description="Margin recovered. Real, but contingent on conversion."
    )
    year_one_net: float
    payback_months: float | None = Field(
        default=None, description="None when the process never pays back."
    )

    hours_released_per_year: float

    def pays_back(self) -> bool:
        return self.payback_months is not None


class SensitivityBand(BaseModel):
    """Base case flanked by a deliberately unkind and a generous scenario."""

    pessimistic: ROIResult
    base: ROIResult
    optimistic: ROIResult

    @property
    def saving_range(self) -> tuple[float, float]:
        return (
            self.pessimistic.gross_annual_saving,
            self.optimistic.gross_annual_saving,
        )


class Risk(BaseModel):
    description: str
    mitigation: str
    severity: str = Field(description="low | medium | high")


class Opportunity(BaseModel):
    """One ranked automation candidate, start to finish."""

    rank: int = Field(ge=1)
    title: str
    thesis: str

    process: ProcessProfile
    design: AutomationDesign
    roi: SensitivityBand | None = None

    risks: list[Risk] = Field(default_factory=list)
    evidence: list[Evidence] = Field(default_factory=list)

    def sourced_evidence(self) -> list[Evidence]:
        return [e for e in self.evidence if e.is_citable()]


class OrganisationScope(BaseModel):
    """The subject of the brief."""

    organisation: str
    business_unit: str
    sector: str
    geography: str
    public_facts: list[Evidence] = Field(default_factory=list)


class Brief(BaseModel):
    """The finished deliverable."""

    scope: OrganisationScope
    thesis: str
    opportunities: list[Opportunity]
    horizon_30_60_90: list[str] = Field(default_factory=list)
    author_note: str = ""

    def total_base_saving(self) -> float:
        return sum(
            o.roi.base.gross_annual_saving for o in self.opportunities if o.roi is not None
        )
