# automotive-ops-intelligence

Produces a ranked, costed AI/automation opportunity brief for a business unit — the kind of document a leadership team can actually fund a decision from.

**Agents supply assumptions. Deterministic Python computes the return.** That split is the entire design. A business case whose numbers came out of a language model cannot be audited, cannot be reproduced, and will not survive its first serious question from a finance director.

```bash
uv sync && uv run python -m automotive_ops_intelligence --offline
```

Runs with no API key. The offline path is fixture-backed and fully deterministic — clone it and see the output.

📄 **[Worked example: Legend Motors (Dubai)](examples/legend-motors-brief.md)**

---

## Why this exists

Ask a language model for a business case and it will give you a confident number with no derivation, no sensitivity, and no way to tell which input is load-bearing. It reads well and it is unfalsifiable, which is the worst possible combination for a document meant to move capital.

So the model never touches the arithmetic here. Agents do what they are good at — reading a sector, decomposing a process, estimating what share of it could be automated — and emit **typed assumptions**. [`roi.py`](src/automotive_ops_intelligence/roi.py) turns those into a number the same way every time, exposing every intermediate.

The result is a brief where an argument about the conclusion becomes an argument about a specific named assumption. That is a much better argument to be having.

## Architecture

```
  ┌──────────────────────── CrewAI Flow ─────────────────────────┐
  │                                                              │
  │  @start   scope_organisation ──▶ Crew: Sector Researcher     │
  │                    │                                         │
  │  @listen  profile_processes ──▶ Crew: Process Analyst        │
  │                    │                 + Automation Architect  │
  │                    ▼                                         │
  │  @router  evidence_gate                                      │
  │            ├── sufficient_evidence ──▶ price_opportunities   │
  │            └── insufficient_evidence ─▶ report_gaps          │
  └──────────────────────────────┬───────────────────────────────┘
                                 │  typed assumptions
                                 ▼
              ┌──────────── roi.py (no LLM) ─────────────┐
              │  cost bridge · cash/opportunity split    │
              │  sensitivity band · payback · ranking    │
              └──────────────────────────────────────────┘
                                 │
                                 ▼
                          render.py ──▶ markdown brief
```

### The evidence gate

The one branch that matters. If the research step could not source enough of its claims, the Flow **refuses to price anything** and emits a gap report instead.

A brief built on unsourced assumptions is worse than no brief, because it is confidently wrong in a format that invites decisions. Making that refusal a routing decision rather than a footnote is the difference between a tool that has judgment and a tool that has a disclaimer.

### Cash versus opportunity

Every process declares whether its error cost is **cash** (demurrage, rework, penalties — money leaving the business) or **opportunity** (a lost lead, a mispriced unit — margin never captured).

Both are real. They are not equally bankable, and payback is computed on cash alone, because funding a build out of margin you hope to capture is how these projects get cancelled in month nine.

This is not academic. In the worked example, classifying lead-triage savings correctly as contingent margin **moved that opportunity from first place to third** — it had the largest headline number and the weakest cash case.

### Ranking on the pessimistic case

Opportunities are ranked by their *pessimistic* cash saving, not the base case. An opportunity that only looks good under generous assumptions is not the one to start with.

## Usage

```bash
# worked example, no API key required
uv run python -m automotive_ops_intelligence --offline

# write to a file
uv run python -m automotive_ops_intelligence --offline --out brief.md

# live: research an organisation and profile named processes
export OPENAI_API_KEY=...
uv run python -m automotive_ops_intelligence \
  --org "Acme Logistics, freight forwarding division" \
  --process "customs declaration preparation" \
  --process "carrier invoice reconciliation" \
  --model gpt-4o-mini

uv run python -m automotive_ops_intelligence --list-fixtures
```

Any [LiteLLM](https://docs.litellm.ai/docs/providers) model identifier works via `--model`.

### Docker

```bash
docker build -t automotive-ops-intelligence .
docker run --rm automotive-ops-intelligence --offline
```

## Adding a fixture

Fixtures are validated through the same Pydantic contract a crew's output is, so a malformed fixture fails loudly rather than producing a subtly wrong brief. Drop a JSON file in [`src/automotive_ops_intelligence/fixtures/`](src/automotive_ops_intelligence/fixtures/) matching the `scope` / `opportunities` shape and it is discoverable immediately.

## Tests

```bash
uv run pytest
```

21 tests. The ROI arithmetic is pinned — the point of computing return in plain Python rather than asking a model for it is that the result is checkable, so it is checked. Tests also assert that no claim labelled `sourced` is missing its URL, which is the failure mode this whole design is built to prevent.

## Scope and honesty

- The **worked example is an outside-in analysis** built entirely from public sources. I have no internal data on the organisation in it. Volumes come from published figures where they exist; everything else is labelled `assumed` and stress-tested in the sensitivity band.
- **Assumed inputs are judgment, not measurement.** They are printed in the brief rather than hidden in an appendix, precisely so they can be challenged.
- The ROI model prices **labour and error cost only**. Revenue upside, working-capital effects and customer-satisfaction gains are real but unfalsifiable at proposal stage, so they are excluded rather than estimated.
- `Confidence` is deliberately coarse — `sourced` / `inferred` / `assumed`. A model asked for a percentage confidence will happily produce 73% and mean nothing by it.

Built July 2026. Design notes and tradeoffs in [`DECISIONS.md`](DECISIONS.md).

## License

MIT
