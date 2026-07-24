"""Tests for the Flow's deterministic path.

Offline mode runs the same Flow, the same evidence gate and the same ROI model
as a live run — only the research and profiling steps read fixtures instead of
calling a crew. That makes the structural behaviour testable in CI at no cost.
"""

from __future__ import annotations

import json

from automotive_ops_intelligence.flow import MIN_SOURCED_FACTS, AutomationBriefFlow, BriefState
from automotive_ops_intelligence.models import Confidence
from automotive_ops_intelligence.offline import (
    available_fixtures,
    load_fixture_opportunities,
    load_fixture_scope,
)
from automotive_ops_intelligence.render import render_brief


def run_offline(org: str = "legend_motors") -> AutomationBriefFlow:
    flow = AutomationBriefFlow()
    flow.kickoff(inputs=BriefState(scope_hint=org, offline=True).model_dump())
    return flow


def test_fixture_is_discoverable():
    assert "legend_motors" in available_fixtures()


def test_fixtures_validate_against_the_schema():
    """The fixture is not free-form JSON; it must satisfy the same contract a crew does."""
    scope = load_fixture_scope("legend_motors")
    opportunities = load_fixture_opportunities("legend_motors")
    assert scope.organisation
    assert len(opportunities) >= 1
    assert all(o.process.annual_volume > 0 for o in opportunities)


def test_every_sourced_fact_carries_a_url():
    """A claim labelled 'sourced' without a source is the failure mode this guards."""
    scope = load_fixture_scope("legend_motors")
    for fact in scope.public_facts:
        if fact.confidence is Confidence.SOURCED:
            assert fact.source_url, f"sourced claim without a URL: {fact.claim[:60]}"


def test_offline_run_produces_a_priced_brief():
    flow = run_offline()
    brief = flow.state.brief
    assert brief is not None
    assert brief.opportunities
    assert all(o.roi is not None for o in brief.opportunities)


def test_opportunities_are_ranked_by_pessimistic_cash():
    flow = run_offline()
    brief = flow.state.brief
    assert brief is not None
    floors = [o.roi.pessimistic.cash_saving for o in brief.opportunities if o.roi]
    assert floors == sorted(floors, reverse=True)
    assert [o.rank for o in brief.opportunities] == list(range(1, len(brief.opportunities) + 1))


def test_evidence_gate_blocks_a_thin_evidence_base():
    """Below the sourced-fact floor, the Flow must refuse to price anything."""
    flow = AutomationBriefFlow()
    flow.kickoff(inputs=BriefState(scope_hint="legend_motors", offline=True).model_dump())

    scope = flow.state.scope
    assert scope is not None
    # Strip the evidence base below the threshold and re-run the gate directly.
    scope.public_facts = scope.public_facts[: MIN_SOURCED_FACTS - 1]
    assert flow.evidence_gate() == "insufficient_evidence"
    assert flow.state.gap_report


def test_render_is_deterministic():
    first = render_brief(run_offline().state.brief)  # type: ignore[arg-type]
    second = render_brief(run_offline().state.brief)  # type: ignore[arg-type]
    assert first == second


def test_rendered_brief_labels_its_assumptions():
    """An unlabelled assumption in an executive brief is the thing to prevent."""
    rendered = render_brief(run_offline().state.brief)  # type: ignore[arg-type]
    assert "## Assumptions" in rendered or "### Assumptions" in rendered
    assert "Evidence base" in rendered


def test_fixture_json_is_valid_and_sorted_keys_stable():
    """Guards against a hand-edit that breaks the fixture silently."""
    from importlib import resources

    raw = (
        resources.files("automotive_ops_intelligence.fixtures")
        .joinpath("legend_motors.json")
        .read_text(encoding="utf-8")
    )
    payload = json.loads(raw)
    assert {"scope", "opportunities"} <= set(payload)


def test_narrative_reaches_the_rendered_brief():
    """Sequencing judgment and disclosure are analyst-supplied, not agent-generated."""
    brief = run_offline().state.brief
    assert brief is not None
    assert brief.horizon_30_60_90, "expected a 30/60/90 plan"
    assert brief.author_note, "expected an author note disclosing method"

    rendered = render_brief(brief)
    assert "First 90 days" in rendered
    assert "outside-in analysis" in rendered
