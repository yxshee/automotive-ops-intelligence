"""Render a Brief to markdown.

Presentation is deliberately separate from computation. Rounding happens here
and nowhere else, so the numbers in `roi.py` stay exact and every figure a
reader sees can be traced back to an unrounded intermediate.

The renderer prints assumptions inline rather than relegating them to an
appendix. An executive brief that hides its assumptions is asking to be trusted
instead of checked, and the whole value of this format is that it can be
checked.
"""

from __future__ import annotations

from automotive_ops_intelligence.models import (
    Brief,
    Confidence,
    Evidence,
    Opportunity,
    ROIResult,
)


def render_brief(brief: Brief) -> str:
    scope = brief.scope
    lines: list[str] = [
        f"# AI and automation opportunities — {scope.organisation}",
        "",
        f"**Business unit:** {scope.business_unit}  ",
        f"**Sector:** {scope.sector}  ",
        f"**Geography:** {scope.geography}",
        "",
        "---",
        "",
        "## Thesis",
        "",
        brief.thesis,
        "",
    ]

    if brief.opportunities:
        lines += _render_summary_table(brief)

    for opportunity in brief.opportunities:
        lines += _render_opportunity(opportunity)

    if brief.horizon_30_60_90:
        lines += ["## First 90 days", ""]
        lines += [f"{i}. {step}" for i, step in enumerate(brief.horizon_30_60_90, 1)]
        lines += [""]

    lines += _render_evidence_section(scope.public_facts)

    if brief.author_note:
        lines += ["## Notes", "", brief.author_note, ""]

    return "\n".join(lines)


def _render_summary_table(brief: Brief) -> list[str]:
    currency = brief.opportunities[0].roi.base.currency if brief.opportunities[0].roi else ""
    lines = [
        "## Summary",
        "",
        f"| # | Opportunity | Total saving ({currency}) | of which cash | Payback | Cash floor |",
        "|---|---|---|---|---|---|",
    ]
    for o in brief.opportunities:
        if o.roi is None:
            lines.append(f"| {o.rank} | {o.title} | not priced | — | — | — |")
            continue
        low, high = o.roi.saving_range
        payback = (
            f"{o.roi.base.payback_months:.0f} mo"
            if o.roi.base.pays_back()
            else "no cash payback"
        )
        floor = (
            f"{o.roi.pessimistic.cash_saving:,.0f}"
            if o.roi.pessimistic.cash_saving > 0
            else "negative"
        )
        lines.append(
            f"| {o.rank} | {o.title} | {low:,.0f} – {high:,.0f} "
            f"| {o.roi.base.cash_saving:,.0f} | {payback} | {floor} |"
        )

    lines += [
        "",
        "Ranked on **pessimistic cash saving**, not on the base-case total. Two "
        "deliberate choices: the pessimistic case, because an opportunity that "
        "only looks good under generous assumptions is not the one to start "
        "with; and cash rather than total, because ranking on recovered margin "
        "would simply promote whichever process carried the most flattering "
        "conversion assumption.",
        "",
        "**Cash** is money that stops leaving the business — labour released, "
        "demurrage and rework avoided, net of run cost. **Opportunity** is "
        "margin recovered, which is real but contingent on a conversion "
        "assumption and should be discounted accordingly.",
        "",
    ]
    return lines


def _render_opportunity(o: Opportunity) -> list[str]:
    lines = [
        "---",
        "",
        f"## {o.rank}. {o.title}",
        "",
        o.thesis,
        "",
        "### Current process",
        "",
        o.process.description,
        "",
        f"- **Annual volume:** {o.process.annual_volume:,} units",
        f"- **Touch time:** {o.process.minutes_per_unit_manual:g} min/unit",
        f"- **Fully loaded cost:** {o.process.currency} "
        f"{o.process.fully_loaded_hourly_cost:,.0f}/hour",
        f"- **Error rate:** {o.process.error_rate:.0%} at "
        f"{o.process.currency} {o.process.cost_per_error:,.0f} per occurrence "
        f"({o.process.error_cost_basis.value} cost)",
        "",
        "### Proposed approach",
        "",
        o.design.approach,
        "",
        f"**Human in the loop.** {o.design.human_in_the_loop}",
        "",
        f"- Automatable share: {o.design.automatable_share:.0%}",
        f"- Realistic first-year adoption: {o.design.adoption_rate:.0%} "
        f"(effective coverage "
        f"{o.design.automatable_share * o.design.adoption_rate:.0%})",
        f"- Residual review time: {o.design.minutes_per_unit_assisted:g} min/unit",
        f"- Residual error rate: {o.design.residual_error_rate:.0%}",
        "",
    ]

    if o.roi is not None:
        lines += _render_roi(o)

    if o.risks:
        lines += ["### Risks", ""]
        for risk in o.risks:
            lines += [
                f"**{risk.severity.upper()} — {risk.description}**",
                "",
                f"> {risk.mitigation}",
                "",
            ]

    assumptions = [e for e in o.process.evidence if e.confidence is not Confidence.SOURCED]
    sourced = [e for e in o.process.evidence if e.confidence is Confidence.SOURCED]

    if sourced:
        lines += ["### Sourced inputs", ""]
        lines += [f"- {_format_evidence(e)}" for e in sourced]
        lines += [""]

    if assumptions:
        lines += [
            "### Assumptions",
            "",
            "These are inputs we chose, not measurements. They are the figures to "
            "challenge first, and they are what the sensitivity band flexes.",
            "",
        ]
        lines += [f"- {_format_evidence(e)}" for e in assumptions]
        lines += [""]

    return lines


def _render_roi(o: Opportunity) -> list[str]:
    assert o.roi is not None
    band = o.roi
    base = band.base
    currency = base.currency

    lines = [
        "### Business case",
        "",
        "| | Pessimistic | Base | Optimistic |",
        "|---|---|---|---|",
        f"| Total annual saving | {_money(band.pessimistic.gross_annual_saving, currency)} "
        f"| {_money(base.gross_annual_saving, currency)} "
        f"| {_money(band.optimistic.gross_annual_saving, currency)} |",
        f"| — of which cash | {_money(band.pessimistic.cash_saving, currency)} "
        f"| {_money(base.cash_saving, currency)} "
        f"| {_money(band.optimistic.cash_saving, currency)} |",
        f"| — of which opportunity | {_money(band.pessimistic.opportunity_saving, currency)} "
        f"| {_money(base.opportunity_saving, currency)} "
        f"| {_money(band.optimistic.opportunity_saving, currency)} |",
        f"| Year-one net | {_money(band.pessimistic.year_one_net, currency)} "
        f"| {_money(base.year_one_net, currency)} "
        f"| {_money(band.optimistic.year_one_net, currency)} |",
        f"| Payback | {_payback(band.pessimistic)} | {_payback(base)} "
        f"| {_payback(band.optimistic)} |",
        "",
        "Cost bridge, base case:",
        "",
        f"- Baseline labour: {_money(base.baseline.labour_cost, currency)}",
        f"- Baseline error cost: {_money(base.baseline.error_cost, currency)}",
        f"- **Baseline total: {_money(base.baseline.total, currency)}**",
        f"- Projected labour: {_money(base.projected.labour_cost, currency)}",
        f"- Projected error cost: {_money(base.projected.error_cost, currency)}",
        f"- Projected run cost: {_money(base.projected.run_cost, currency)}",
        f"- **Projected total: {_money(base.projected.total, currency)}**",
        "",
        f"Roughly {base.hours_released_per_year:,.0f} staff-hours released per year, "
        f"against a one-time build of {_money(o.design.build_cost, currency)}.",
        "",
        "The model prices labour and error cost only. Revenue upside, "
        "working-capital effects and customer-satisfaction gains are real but "
        "unfalsifiable at proposal stage, so they are excluded rather than "
        "estimated.",
        "",
    ]
    return lines


def _render_evidence_section(facts: list[Evidence]) -> list[str]:
    if not facts:
        return []

    lines = ["---", "", "## Evidence base", ""]
    for label, confidence in (
        ("Sourced", Confidence.SOURCED),
        ("Inferred", Confidence.INFERRED),
        ("Assumed", Confidence.ASSUMED),
    ):
        subset = [f for f in facts if f.confidence is confidence]
        if not subset:
            continue
        lines += [f"### {label}", ""]
        lines += [f"- {_format_evidence(f)}" for f in subset]
        lines += [""]
    return lines


def _format_evidence(evidence: Evidence) -> str:
    if evidence.source_url:
        return f"{evidence.claim} [(source)]({evidence.source_url})"
    return f"{evidence.claim} *({evidence.confidence.value})*"


def _money(value: float, currency: str) -> str:
    sign = "-" if value < 0 else ""
    return f"{sign}{currency} {abs(value):,.0f}"


def _payback(result: ROIResult) -> str:
    return f"{result.payback_months:.0f} mo" if result.pays_back() else "no payback"
