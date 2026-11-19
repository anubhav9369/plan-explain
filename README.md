# plan-explain

Explain an InspectablePlan in plain English, so a human can decide
without reading JSON.

An approver should not need to parse a plan file to know what they are
agreeing to. This tool turns a plan into a short readable explanation:
what the plan will do, why each step exists, what it will cost, what
could go wrong, and what to check before approving.

It explains only. It never approves anything itself — the decision
still goes through `plan-approve`, the numbers come from
`plan-cost-estimate`, and the risk findings from `plan-risk-scan`.
This is the words around them.

Part of [BRJP26100123](https://github.com/anubhav9369/trustworthy-agentic-ai)
— Building Trustworthy AI Systems through Explainability and
Human-in-the-Loop Control. Week 2: human-in-the-loop.

## Usage

```bash
python3 plan_explain.py examples/plan.json
python3 plan_explain.py examples/plan.json --json
```

Exit codes: `0` explanation written, `2` input error.

## What the explanation covers

- **What it will do** — each step in one sentence, with its reason;
  steps that cannot be undone say so, and gated steps say they wait
  for your permission
- **What it will cost** — totals in dollars and minutes; a step with no
  estimate is unknown, not zero
- **What could go wrong** — ungated irreversible steps are HIGH; steps
  with no reason, no estimate, gated steps with no failure points, and
  a plan with no constraints are MEDIUM
- **Before you decide** — a short checklist, ending in a one-line
  bottom line

## Examples

- `examples/plan.json` — clean v2: the send step cannot be undone but
  waits for permission. Explanation: nothing flagged.
- `examples/risky-plan.json` — ungated publish step with no reason.
  Explanation: one HIGH concern, bottom line says do not approve.
- `examples/explanation.md`, `examples/risky-explanation.md` — the
  generated explanations.

## Tests

```bash
python3 -m unittest discover -s tests -v
```

10 tests, standard library only.
