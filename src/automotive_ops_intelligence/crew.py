"""The research crew.

Four agents, each with a narrow remit. The division is not cosmetic — it exists
so that the agent estimating how much of a process is automatable is not the
same agent arguing the opportunity is worth doing. Asking one agent to both
propose and appraise reliably produces optimistic appraisals.

Note what these agents are *not* asked to do: none of them computes a return.
They supply assumptions. `roi.py` does the arithmetic.
"""

from __future__ import annotations

from crewai import Agent, Crew, Process, Task

from automotive_ops_intelligence.models import (
    AutomationDesign,
    OrganisationScope,
    ProcessProfile,
)

DEFAULT_MODEL = "gpt-4o-mini"


def build_agents(model: str = DEFAULT_MODEL) -> dict[str, Agent]:
    researcher = Agent(
        role="Sector Research Analyst",
        goal=(
            "Establish what is publicly known and verifiable about the target "
            "organisation and its sector. Separate cited fact from inference."
        ),
        backstory=(
            "You have been burned before by a brief that asserted a number "
            "nobody could source. You now label every claim with its provenance "
            "and would rather report 'not found' than guess. You treat an "
            "organisation's own press releases as evidence of intent, not of "
            "outcome."
        ),
        llm=model,
        verbose=False,
        allow_delegation=False,
    )

    process_analyst = Agent(
        role="Operations Process Analyst",
        goal=(
            "Decompose the business unit into concrete, high-volume processes and "
            "estimate the cost shape of each: volume, touch time, error rate, "
            "cost of an error."
        ),
        backstory=(
            "You have spent enough time on operations floors to know that the "
            "expensive process is rarely the one leadership names first. You look "
            "for volume multiplied by touch time, and you are explicit about which "
            "of your numbers are measured and which are assumed."
        ),
        llm=model,
        verbose=False,
        allow_delegation=False,
    )

    automation_architect = Agent(
        role="Automation Architect",
        goal=(
            "For each candidate process, propose a concrete technical approach and "
            "state honestly what share of volume it could handle end-to-end, what "
            "a human must still approve, and where it would fail."
        ),
        backstory=(
            "You have shipped enough automation to distrust demos. You assume "
            "adoption will lag capability, that exceptions are the real cost "
            "centre, and that any system touching money or regulatory documents "
            "needs a human approval gate. You state residual error rates rather "
            "than implying zero."
        ),
        llm=model,
        verbose=False,
        allow_delegation=False,
    )

    critic = Agent(
        role="Business Case Critic",
        goal=(
            "Attack the proposed opportunities. Find the overstated assumption, "
            "the missing cost, the process that is already someone else's project, "
            "and the risk nobody priced."
        ),
        backstory=(
            "You review capital requests for a living and you have seen every "
            "flattering assumption there is. You are not contrarian for its own "
            "sake — you are the reason the number survives contact with a CFO."
        ),
        llm=model,
        verbose=False,
        allow_delegation=False,
    )

    return {
        "researcher": researcher,
        "process_analyst": process_analyst,
        "automation_architect": automation_architect,
        "critic": critic,
    }


def build_scoping_crew(scope_hint: str, model: str = DEFAULT_MODEL) -> Crew:
    """Establish the public factual base for the organisation."""
    agents = build_agents(model)

    research_task = Task(
        description=(
            f"Research this organisation and business unit:\n\n{scope_hint}\n\n"
            "Establish: what it actually does, its operational scale, its stated "
            "expansion plans, and any public signal about technology or automation "
            "intent. Every claim must carry a source URL and a confidence label of "
            "sourced, inferred, or assumed. Where you cannot verify something, say "
            "so explicitly rather than filling the gap."
        ),
        expected_output=(
            "An OrganisationScope with public_facts populated, each fact labelled "
            "with its confidence and a source URL where one exists."
        ),
        agent=agents["researcher"],
        output_pydantic=OrganisationScope,
    )

    return Crew(
        agents=[agents["researcher"]],
        tasks=[research_task],
        process=Process.sequential,
        verbose=False,
    )


def build_opportunity_crew(
    scope: OrganisationScope,
    process_hint: str,
    model: str = DEFAULT_MODEL,
) -> Crew:
    """Profile one candidate process and design an automation for it."""
    agents = build_agents(model)

    profile_task = Task(
        description=(
            f"Organisation: {scope.organisation} / {scope.business_unit} "
            f"({scope.sector}, {scope.geography}).\n\n"
            f"Candidate process: {process_hint}\n\n"
            "Produce a ProcessProfile. Estimate annual volume, human touch time "
            "per unit in minutes, fully loaded hourly cost in local currency, the "
            "current error rate, and the cost of a single error. Ground volume in "
            "the organisation's published figures where possible. Label every "
            "estimate you could not source as assumed — these become the inputs "
            "that get stress-tested, so an unlabelled guess is worse than a "
            "labelled one."
        ),
        expected_output="A fully populated ProcessProfile with evidence attached.",
        agent=agents["process_analyst"],
        output_pydantic=ProcessProfile,
    )

    design_task = Task(
        description=(
            "Design an automation for the process profiled in the previous task.\n\n"
            "State the approach concretely — what the system reads, what it "
            "decides, what it writes. Then estimate: what share of volume it can "
            "handle end-to-end, what adoption rate is realistic in the first year "
            "(this is almost never the same as the automatable share), residual "
            "human review time per unit, and the residual error rate on the "
            "automated path.\n\n"
            "Specify the human-in-the-loop gate explicitly: what must a person "
            "approve, and above what threshold. Do not propose a design with no "
            "human gate on a process that touches money, customs, or regulatory "
            "filings.\n\n"
            "Estimate build cost, annual platform cost, and per-unit inference "
            "cost. Do NOT compute a return on investment — that is calculated "
            "downstream from your assumptions."
        ),
        expected_output="A fully populated AutomationDesign.",
        agent=agents["automation_architect"],
        context=[profile_task],
        output_pydantic=AutomationDesign,
    )

    return Crew(
        agents=[agents["process_analyst"], agents["automation_architect"]],
        tasks=[profile_task, design_task],
        process=Process.sequential,
        verbose=False,
    )
