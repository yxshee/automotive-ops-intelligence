"""Fixture-backed offline mode.

The Flow runs identically with or without a model. Offline, the research and
profiling steps read validated fixtures instead of calling a crew; everything
downstream — the evidence gate, the ROI model, ranking, rendering — is the same
code on the same code path.

This exists for three reasons. A reviewer can clone the repository and run it
without an API key. The deterministic half of the pipeline is testable in CI at
zero cost and zero flake. And the fixtures double as a worked example of what
good agent output looks like, which is the thing a schema alone cannot express.
"""

from __future__ import annotations

import json
from functools import lru_cache
from importlib import resources
from pathlib import Path

from automotive_ops_intelligence.models import Opportunity, OrganisationScope

FIXTURE_PACKAGE = "automotive_ops_intelligence.fixtures"
DEFAULT_FIXTURE = "legend_motors"


class FixtureNotFound(LookupError):
    """Raised when a requested fixture does not exist."""


@lru_cache(maxsize=8)
def _load(name: str) -> dict:
    slug = _slugify(name)
    try:
        source = resources.files(FIXTURE_PACKAGE).joinpath(f"{slug}.json")
        return json.loads(source.read_text(encoding="utf-8"))
    except (FileNotFoundError, ModuleNotFoundError) as exc:
        available = ", ".join(available_fixtures()) or "none"
        raise FixtureNotFound(f"No fixture named {slug!r}. Available: {available}.") from exc


def available_fixtures() -> list[str]:
    try:
        root = resources.files(FIXTURE_PACKAGE)
    except ModuleNotFoundError:
        return []
    return sorted(Path(str(p)).stem for p in root.iterdir() if str(p).endswith(".json"))


def load_fixture_scope(name: str = DEFAULT_FIXTURE) -> OrganisationScope:
    """Return the organisation scope, validated through the same schema a crew fills."""
    return OrganisationScope.model_validate(_load(name)["scope"])


def load_fixture_opportunities(name: str = DEFAULT_FIXTURE) -> list[Opportunity]:
    """Return unpriced opportunities. ROI is computed by the Flow, never stored here."""
    payload = _load(name)
    return [Opportunity.model_validate(o) for o in payload["opportunities"]]


def load_fixture_narrative(name: str = DEFAULT_FIXTURE) -> dict:
    """Return the analyst-supplied narrative: sequencing judgment and disclosures.

    Deliberately not agent-generated. Which opportunity to start with is a
    judgment about organisational readiness and political capital, not something
    that falls out of a payback calculation — the highest-return opportunity and
    the right first project are frequently different things.
    """
    payload = _load(name)
    return {
        "horizon_30_60_90": payload.get("horizon_30_60_90", []),
        "author_note": payload.get("author_note", ""),
    }


def _slugify(name: str) -> str:
    """Map a loose organisation hint onto a fixture filename."""
    if not name:
        return DEFAULT_FIXTURE

    slug = "".join(c.lower() if c.isalnum() else "_" for c in name).strip("_")
    while "__" in slug:
        slug = slug.replace("__", "_")

    if slug in available_fixtures():
        return slug

    # Allow "Legend Motors" or "legend" to resolve to legend_motors.
    for candidate in available_fixtures():
        if slug and (slug in candidate or candidate.startswith(slug.split("_")[0])):
            return candidate

    return slug
