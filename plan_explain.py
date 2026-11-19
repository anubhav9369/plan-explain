#!/usr/bin/env python3
"""plan-explain: explain an InspectablePlan in plain English.

An approver should not need to read JSON to decide. This tool turns a
plan into a short human-readable explanation: what the plan will do,
why each step exists, what it will cost, what could go wrong, and what
to check before approving.

It explains only. It never approves anything itself; the decision still
goes through plan-approve, and the numbers come from plan-cost-estimate
and the findings from plan-risk-scan. This is the words around them.

Usage:
  python3 plan_explain.py examples/plan.json
  python3 plan_explain.py examples/plan.json --json

Exit codes: 0 explanation written, 2 input error.
Standard library only.
"""
import argparse
import json
import sys

IRREVERSIBLE_WORD = "cannot be undone"


class PlanError(Exception):
    """Raised when the plan file cannot be read or understood."""


def load_plan(path):
    try:
        with open(path, encoding="utf-8") as f:
            plan = json.load(f)
    except FileNotFoundError:
        raise PlanError(f"no such file: {path}")
    except json.JSONDecodeError as exc:
        raise PlanError(f"{path} is not valid JSON: {exc}")
    if not isinstance(plan, dict):
        raise PlanError("plan must be a JSON object")
    if not isinstance(plan.get("steps"), list) or not plan["steps"]:
        raise PlanError("plan must have a non-empty 'steps' list")
    if not plan.get("goal"):
        raise PlanError("plan must have a 'goal'")
    return plan


def explain_step(step, index):
    """One step, in plain English, with its warnings attached."""
    action = step.get("action", "(no action given)")
    why = step.get("why")
    estimate = step.get("estimate") or {}
    lines = [f"Step {index + 1} — {action}."]
    if why:
        lines.append(f"Why: {why}.")
    else:
        lines.append("No reason given for this step.")
    if step.get("irreversible"):
        if step.get("permission_gated"):
            lines.append(
                f"This step {IRREVERSIBLE_WORD}, but it waits for your "
                "permission before it runs."
            )
        else:
            lines.append(
                f"This step {IRREVERSIBLE_WORD} and runs without asking "
                "your permission first."
            )
    elif step.get("permission_gated"):
        lines.append("This step waits for your permission before it runs.")
    if estimate.get("usd") is None and estimate.get("minutes") is None:
        lines.append("No cost or time estimate — the price is unknown.")
    else:
        bits = []
        if estimate.get("usd") is not None:
            bits.append(f"${estimate['usd']:.2f}")
        if estimate.get("minutes") is not None:
            bits.append(f"about {estimate['minutes']} minutes")
        lines.append("Estimated cost: " + ", ".join(bits) + ".")
    if step.get("permission_gated") and not step.get("failure_points"):
        lines.append("No failure points listed, so nobody has said what "
                     "could go wrong here.")
    return {
        "id": step.get("id", f"step-{index + 1}"),
        "text": " ".join(lines),
        "irreversible": bool(step.get("irreversible")),
        "permission_gated": bool(step.get("permission_gated")),
        "has_why": bool(why),
        "has_estimate": estimate.get("usd") is not None
        or estimate.get("minutes") is not None,
    }


def explain(plan):
    steps = [explain_step(s, i) for i, s in enumerate(plan["steps"])]
    total_usd = 0.0
    total_minutes = 0
    unknown = []
    for step, raw in zip(steps, plan["steps"]):
        estimate = raw.get("estimate") or {}
        if estimate.get("usd") is not None:
            total_usd += estimate["usd"]
        if estimate.get("minutes") is not None:
            total_minutes += estimate["minutes"]
        if not step["has_estimate"]:
            unknown.append(step["id"])

    concerns = []
    for step, raw in zip(steps, plan["steps"]):
        if step["irreversible"] and not step["permission_gated"]:
            concerns.append({
                "severity": "HIGH",
                "text": f"Step {step['id']} does something that "
                        f"{IRREVERSIBLE_WORD} and runs without your "
                        "permission.",
            })
        if step["permission_gated"] and not raw.get("failure_points"):
            concerns.append({
                "severity": "MEDIUM",
                "text": f"Step {step['id']} waits for your permission, but "
                        "nobody listed what could go wrong with it.",
            })
        if not step["has_why"]:
            concerns.append({
                "severity": "MEDIUM",
                "text": f"Step {step['id']} has no reason written down — "
                        "you cannot tell why it is in the plan.",
            })
        if not step["has_estimate"]:
            concerns.append({
                "severity": "MEDIUM",
                "text": f"Step {step['id']} has no cost or time estimate — "
                        "its price is unknown, not zero.",
            })
    if not plan.get("constraints"):
        concerns.append({
            "severity": "MEDIUM",
            "text": "The plan lists no constraints — nothing says what it "
                    "must not do.",
        })

    checklist = [
        "Read each step's reason and check it matches the goal.",
        "Check every step that cannot be undone — is it permission-gated?",
        "Ask for an estimate on any step priced as unknown.",
    ]
    if concerns:
        checklist.append("Work through the concerns below before deciding.")

    high = [c for c in concerns if c["severity"] == "HIGH"]
    if high:
        bottom_line = ("Do not approve this plan as written — fix the HIGH "
                       "concerns first.")
    elif concerns:
        bottom_line = ("Nothing here blocks approval outright, but check the "
                       "concerns below before you decide.")
    else:
        bottom_line = ("Nothing in this plan needs a warning — read the "
                       "steps and decide.")

    goal = plan["goal"]
    return {
        "plan_id": plan.get("id"),
        "version": plan.get("version"),
        "summary": f"This plan will {goal} in {len(steps)} steps.",
        "steps": steps,
        "cost": {
            "total_usd": round(total_usd, 2),
            "total_minutes": total_minutes,
            "unknown_steps": unknown,
        },
        "constraints": list(plan.get("constraints") or []),
        "assumptions": list(plan.get("assumptions") or []),
        "concerns": concerns,
        "checklist": checklist,
        "bottom_line": bottom_line,
    }


def render_markdown(exp):
    out = [f"# Plan explanation"]
    if exp["plan_id"] is not None:
        out.append(f"Plan `{exp['plan_id']}`"
                   + (f" (version {exp['version']})"
                      if exp["version"] is not None else ""))
    out.append("")
    out.append(exp["summary"])
    out.append("")
    out.append("## What it will do")
    out.append("")
    for step in exp["steps"]:
        out.append(f"- {step['text']}")
    out.append("")
    cost = exp["cost"]
    out.append("## What it will cost")
    out.append("")
    out.append(f"Total: ${cost['total_usd']:.2f}, "
               f"about {cost['total_minutes']} minutes.")
    if cost["unknown_steps"]:
        out.append("Unknown price: steps "
                   + ", ".join(cost["unknown_steps"])
                   + " have no estimate — unknown, not zero.")
    out.append("")
    if exp["constraints"]:
        out.append("## What it must not do")
        out.append("")
        for c in exp["constraints"]:
            out.append(f"- {c}")
        out.append("")
    if exp["assumptions"]:
        out.append("## What it assumes")
        out.append("")
        for a in exp["assumptions"]:
            out.append(f"- {a}")
        out.append("")
    out.append("## What could go wrong")
    out.append("")
    if exp["concerns"]:
        for c in exp["concerns"]:
            out.append(f"- **{c['severity']}** — {c['text']}")
    else:
        out.append("Nothing flagged.")
    out.append("")
    out.append("## Before you decide")
    out.append("")
    for item in exp["checklist"]:
        out.append(f"- [ ] {item}")
    out.append("")
    out.append(f"**Bottom line:** {exp['bottom_line']}")
    out.append("")
    return "\n".join(out)


def main(argv=None):
    parser = argparse.ArgumentParser(
        description="Explain an InspectablePlan in plain English.")
    parser.add_argument("plan", help="path to the plan JSON file")
    parser.add_argument("--json", action="store_true",
                        help="print the explanation as JSON instead of Markdown")
    args = parser.parse_args(argv)
    try:
        plan = load_plan(args.plan)
    except PlanError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    exp = explain(plan)
    if args.json:
        print(json.dumps(exp, indent=2))
    else:
        print(render_markdown(exp), end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
