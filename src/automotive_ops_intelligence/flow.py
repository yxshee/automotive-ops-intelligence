"""The orchestration Flow.

CrewAI Flows carry the structure — state, sequencing, and the routing decision.
Crews are invoked from inside a Flow step when the work genuinely needs agents
collaborating. A pipeline of agents with no state and no branching does not need
a Flow, and a Flow whose every branch leads to the same place is decoration.

The one branch that matters here is the evidence gate: if the research step
could not source enough of its claims, the Flow refuses to build a business case
on top of them and routes to a gap report instead. A brief built on unsourced
assumptions is worse than no brief, because it is confidently wrong in a format
that invites decisions.
"""

from __future__ import annotations

from crewai.flow import Flow, listen, router, start
from pydantic import BaseModel, Field

from automotive_ops_intelligence.models import (
    Brief,
    Confidence,
    Opportunity,
    OrganisationScope,
)
from automotive_ops_intelligence.roi import compute_sensitivity

MIN_SOURCED_FACTS = 3
"""Below this, the evidence base is too thin to build a business case on."""


class BriefState(BaseModel):
    """Flow state. Persisted between steps and inspectable after a run."""

    scope_hint: str = ""
    process_hints: list[str] = Field(default_factory=list)
    model: str = "gpt-4o-mini"
    offline: bool = False

    scope: OrganisationScope | None = None
    opportunities: list[Opportunity] = Field(default_factory=list)
    brief: Brief | None = None

    # Narrative the analyst supplies rather than the model: sequencing judgment
    # and any disclosure the reader is owed.
    horizon_30_60_90: list[str] = Field(default_factory=list)
    author_note: str = ""

    gap_report: list[str] = Field(default_factory=list)


class AutomationBriefFlow(Flow[BriefState]):
    """Scope an organisation, profile its processes, and price the opportunities."""

    @start()
    def scope_organisation(self) -> str:
        if self.state.offline:
            from automotive_ops_intelligence.offline import load_fixture_scope

            self.state.scope = load_fixture_scope(self.state.scope_hint)
        else:
            from automotive_ops_intelligence.crew import build_scoping_crew

            crew = build_scoping_crew(self.state.scope_hint, self.state.model)
            result = crew.kickoff()
            self.state.scope = result.pydantic  # type: ignore[assignment]

        return "scoped"

    @listen(scope_organisation)
    def profile_processes(self) -> str:
        assert self.state.scope is not None

        if self.state.offline:
            from automotive_ops_intelligence.offline import (
                load_fixture_narrative,
                load_fixture_opportunities,
            )

            self.state.opportunities = load_fixture_opportunities(self.state.scope_hint)
            narrative = load_fixture_narrative(self.state.scope_hint)
            self.state.horizon_30_60_90 = narrative.get("horizon_30_60_90", [])
            self.state.author_note = narrative.get("author_note", "")
            return "profiled"

        from automotive_ops_intelligence.crew import build_opportunity_crew

        for index, hint in enumerate(self.state.process_hints, start=1):
            crew = build_opportunity_crew(self.state.scope, hint, self.state.model)
            result = crew.kickoff()

            # The crew returns the design; the profile is the first task's output.
            profile = result.tasks_output[0].pydantic
            design = result.tasks_output[-1].pydantic

            self.state.opportunities.append(
                Opportunity(
                    rank=index,
                    title=hint,
                    thesis="",
                    process=profile,  # type: ignore[arg-type]
                    design=design,  # type: ignore[arg-type]
                )
            )

        return "profiled"

    @router(profile_processes)
    def evidence_gate(self) -> str:
        """Refuse to price opportunities that rest on unsourced claims."""
        assert self.state.scope is not None

        sourced = [f for f in self.state.scope.public_facts if f.is_citable()]

        if len(sourced) < MIN_SOURCED_FACTS:
            self.state.gap_report.append(
                f"Only {len(sourced)} sourced fact(s) established; "
                f"{MIN_SOURCED_FACTS} required before pricing an opportunity."
            )
            return "insufficient_evidence"

        unsourced_designs = [
            o.title
            for o in self.state.opportunities
            if not any(e.confidence is Confidence.SOURCED for e in o.process.evidence)
        ]
        if unsourced_designs:
            self.state.gap_report.extend(
                f"Process '{title}' has no sourced volume figure; "
                "its ROI would be assumption on assumption."
                for title in unsourced_designs
            )

        return "sufficient_evidence"

    @listen("sufficient_evidence")
    def price_opportunities(self) -> str:
        """Deterministic ROI. No agent involved past this point."""
        for opportunity in self.state.opportunities:
            opportunity.roi = compute_sensitivity(opportunity.process, opportunity.design)

        # Rank on pessimistic *cash* saving. Two deliberate choices: the
        # pessimistic case, because an opportunity that only looks good under
        # generous assumptions is not the one to start with; and cash rather
        # than gross, because ranking on recovered margin promotes whichever
        # process had the most flattering conversion assumption attached to it.
        self.state.opportunities.sort(
            key=lambda o: o.roi.pessimistic.cash_saving if o.roi else 0.0,
            reverse=True,
        )
        for index, opportunity in enumerate(self.state.opportunities, start=1):
            opportunity.rank = index

        assert self.state.scope is not None
        self.state.brief = Brief(
            scope=self.state.scope,
            thesis=_synthesise_thesis(self.state.opportunities),
            opportunities=self.state.opportunities,
            horizon_30_60_90=self.state.horizon_30_60_90,
            author_note=self.state.author_note,
        )
        return "priced"

    @listen("insufficient_evidence")
    def report_gaps(self) -> str:
        assert self.state.scope is not None
        self.state.brief = Brief(
            scope=self.state.scope,
            thesis=(
                "Insufficient sourced evidence to price these opportunities. "
                "The gaps below must be closed before a business case is credible."
            ),
            opportunities=[],
            author_note="\n".join(self.state.gap_report),
        )
        return "gapped"


def _synthesise_thesis(opportunities: list[Opportunity]) -> str:
    if not opportunities:
        return "No priced opportunities."

    top = opportunities[0]
    band = top.roi
    if band is None:
        return top.title

    low, high = band.saving_range
    currency = band.base.currency

    if not band.base.pays_back():
        return (
            f"The leading candidate is {top.title.lower()}, which does not pay back "
            "on cash within the modelled horizon under current assumptions."
        )

    composition = (
        "all of it cash"
        if band.base.opportunity_saving <= 0
        else f"{currency} {band.base.cash_saving:,.0f} of it cash"
    )
    return (
        f"The strongest candidate on cash return is {top.title.lower()}, worth "
        f"{currency} {low:,.0f}–{high:,.0f} a year depending on adoption — "
        f"{composition} at the base case, paying back the build in "
        f"{band.base.payback_months:.0f} months."
    )
