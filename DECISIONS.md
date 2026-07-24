# Design decisions

What I chose, why, and what it cost.

---

## 1. Agents supply assumptions; deterministic code computes the return

**Decision.** No language model touches any arithmetic. Crews emit typed `ProcessProfile` and `AutomationDesign` objects; `roi.py` turns those into numbers.

**Why.** A business case has to survive a hostile reading by someone whose job is to say no. "The model estimated AED 320,000" is not an answer to "where does that come from?" — but a cost bridge with named inputs is, and it moves the conversation to the assumption that is actually load-bearing.

There is a second reason. Language models are inconsistent at arithmetic in a way that is hard to notice: the failure is a plausible number, not an exception. A wrong ROI figure does not crash anything, it just quietly misallocates capital.

**Cost.** The model shape is fixed. It prices labour and error cost, and anything outside that — revenue upside, working capital, customer satisfaction — cannot be expressed. I think that is correct at proposal stage, since those are the terms most easily inflated, but it does mean the tool understates genuinely revenue-driven opportunities.

---

## 2. Cash and opportunity cost are tracked separately

**Decision.** `ProcessProfile.error_cost_basis` marks each process as `cash` or `opportunity`. Payback is computed on cash alone.

**Why.** This started as a bug I found in my own output. The first run ranked lead triage as the top opportunity at roughly AED 1.9M — until I noticed that its "error cost" was foregone margin on leads that might not have converted anyway, while the export-documentation opportunity it beat was measured in demurrage actually paid.

Adding the distinction moved lead triage from first to third. A CFO would have found that in the first thirty seconds of the meeting, and everything else in the brief would have been read differently afterwards.

**Cost.** It adds a field that whoever profiles a process has to get right, and getting it wrong is silent. A stronger version would refuse to accept `cash` basis without a supporting citation.

---

## 3. Ranking on the pessimistic case

**Decision.** Opportunities sort by pessimistic cash saving, not base-case total.

**Why.** Ranking on the base case systematically promotes whichever opportunity had the most optimistic assumptions attached, because the base case *is* the assumptions. Ranking on the downside asks a better question: which of these still makes sense if I am wrong about the two numbers I am least sure of?

**Cost.** It is conservative in a way that could genuinely mis-rank a high-variance, high-upside opportunity. The full band is always printed, so the base and optimistic cases are one line away — but the default ordering does carry a point of view.

---

## 4. Sensitivity flexes share and adoption, and only inflates build cost

**Decision.** `SensitivityConfig` moves automatable share and adoption rate ±20%. Build cost is multiplied by 1.5 in the pessimistic case and left alone in the optimistic one.

**Why.** Share and adoption are the soft numbers — judgment rather than measurement — and they *multiply*, so error in them compounds rather than averaging out. Build cost gets asymmetric treatment because implementation estimates are reliably optimistic and rarely wrong in the cheap direction. A symmetric band there would be dishonest in a way that flatters the proposal.

**Cost.** ±20% is itself an assumption, and one that is not derived from anything. It is configurable, which is a partial answer, and it is at least visible.

---

## 5. Automatable share and adoption rate are separate inputs

**Decision.** Two fields, multiplied to get effective coverage.

**Why.** The share a system *could* handle and the share an organisation *lets* it handle are different numbers, and conflating them is the single most common way an automation business case overstates its return. A system that handles 80% of volume but is trusted with 60% of eligible cases touches 48% — and the gap between 80% and 48% is a change-management problem, not an engineering one.

Keeping them separate makes that visible in the brief, and it makes adoption something you can argue about on its own terms.

**Cost.** None I can see. This is close to free and I would keep it in any rewrite.

---

## 6. A router that can refuse

**Decision.** `evidence_gate` routes to a gap report instead of a business case when fewer than three claims are properly sourced.

**Why.** A Flow whose every branch leads to the same place is decoration — a linear pipeline wearing a router. The gate is the one place this tool exercises judgment, and it exercises it in the direction of refusing to produce output.

That matters more than it sounds. The natural failure mode of a brief generator is generating a brief regardless, because output feels like success. A confident, well-formatted, unsourced brief is worse than nothing, because the format itself signals a rigour the content does not have.

**Cost.** The threshold is a blunt count. Three well-sourced facts about the wrong things would pass; it measures quantity, not relevance.

---

## 7. Fixtures share the schema with live agent output

**Decision.** Offline fixtures are validated through the same Pydantic models a crew's `output_pydantic` fills.

**Why.** Three things fall out of it. A reviewer can run the tool without an API key. CI can test the entire deterministic half — gate, ROI, ranking, rendering — at zero cost and zero flake. And the fixture doubles as a worked specification of what good agent output looks like, which a bare schema cannot express.

**Cost.** Fixtures drift from real model output. Nothing here proves an actual model can populate these schemas well — only that the structure holds if it does.

---

## 8. Four agents with a critic among them

**Decision.** Researcher, process analyst, automation architect, and a business case critic.

**Why.** The split is not cosmetic. The agent estimating how much of a process is automatable should not be the same agent arguing the opportunity is worth doing — asking one agent to both propose and appraise reliably produces optimistic appraisals.

**Cost.** More agents means more latency and more cost per run, and the critic is currently defined but not yet wired into the Flow's scoring path. That is the most obvious piece of unfinished work here, and I would rather say so than quietly leave it looking intentional.

---

## 9. Coarse confidence labels

**Decision.** `sourced` / `inferred` / `assumed`, and nothing finer.

**Why.** A model asked for numeric confidence will produce 73% and mean nothing by it. Three labels carry the distinction that actually changes what a reader should do: can I check this, did someone reason to it, or did someone choose it?

**Cost.** No way to express "sourced, but from a press release stating intent rather than outcome" — a real distinction in this domain, where announced capacity and delivered capacity differ.

---

## Known gaps

- **The critic agent is defined but not wired into scoring.** Named above; the most visible loose end.
- **No caching between runs.** Re-running a live analysis re-pays for identical research.
- **The evidence gate counts rather than judges.** Quantity of sourcing is a weak proxy for quality of sourcing.
- **No currency handling beyond a label.** Multi-currency inputs would silently produce a meaningless total.
- **Fixture drift is unguarded.** Nothing detects that a fixture no longer resembles what a live crew returns.
