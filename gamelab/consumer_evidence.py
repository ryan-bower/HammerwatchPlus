"""Mechanical reconciliation of reviewed scenario consumers, with no game APIs.

Case reviewers still establish the oracle and its scope. This module establishes
that every declared invocation and consumer row exists in the retained raw return.
"""
from __future__ import annotations

import json


def _same_json(left, right):
    try:
        return json.dumps(left, sort_keys=True, allow_nan=False) == json.dumps(right, sort_keys=True, allow_nan=False)
    except (TypeError, ValueError):
        return False


def validate_consumers(admission, scenario, records):
    """Return a bounded report for parsed bot-results.jsonl records.

The scenario must be the exact retained scenario snapshot, independently pinned
by the caller. Admission is the reviewed case data from the frozen catalog.
There is deliberately no expression evaluator, source import or filesystem read.
"""
    errors, checks = [], []
    if not isinstance(admission, dict) or not isinstance(scenario, dict):
        return {"valid": False, "errors": ["admission and scenario must be objects"], "checks": []}
    steps = scenario.get("steps")
    declarations = admission.get("consumers", [])
    if (not isinstance(steps, list) or len(steps) > 4096
            or not isinstance(records, list) or len(records) > 4096
            or not isinstance(declarations, list) or len(declarations) > 256):
        return {"valid": False, "errors": ["invalid or unbounded steps, records or consumers"], "checks": []}
    bot_steps = [(i, s) for i, s in enumerate(steps) if isinstance(s, dict) and s.get("do") == "bot"]
    if len(records) != len(bot_steps):
        errors.append("completed bot record count differs from scenario invocations")
    bound = {}
    previous_assertion = -1
    for position, ((step_index, step), record) in enumerate(zip(bot_steps, records)):
        if not isinstance(record, dict):
            errors.append(f"invocation {position}: bot record is not an object")
            continue
        assertion = record.get("assertion_index")
        if (record.get("bot") != step.get("bot")
                or not _same_json(record.get("kwargs", {}), step.get("kwargs", {}))
                or type(record.get("pass")) is not int or record["pass"] < 1
                or type(assertion) is not int or assertion <= previous_assertion):
            errors.append(f"step {step_index}: invocation identity, kwargs, pass or assertion order differs")
            continue
        previous_assertion = assertion
        result = record.get("result")
        if not isinstance(result, dict):
            errors.append(f"step {step_index}: completed result is not an object")
            continue
        bound[step_index] = (step, result)
    seen = set()
    for declaration in declarations:
        if not isinstance(declaration, dict) or set(declaration) != {"step", "bot", "rows"}:
            errors.append("consumer declaration requires exact step/bot/rows fields")
            continue
        step_index, bot, wanted = declaration["step"], declaration["bot"], declaration["rows"]
        if (type(step_index) is not int or step_index < 0 or step_index >= len(steps)
                or step_index in seen or not isinstance(bot, str)
                or not isinstance(wanted, list) or not 0 < len(wanted) <= 256
                or any(not isinstance(tag, str) or not tag or len(tag) > 200 for tag in wanted)
                or len(set(wanted)) != len(wanted)):
            errors.append("consumer step, bot or required rows are invalid/duplicate")
            continue
        seen.add(step_index)
        match = bound.get(step_index)
        if match is None or match[0].get("bot") != bot:
            errors.append(f"step {step_index}: declared consumer has no matching completed invocation")
            continue
        result = match[1]
        rows = result.get("rows")
        if (result.get("ok") is not True or not isinstance(rows, list) or len(rows) != len(wanted)
                or not all(isinstance(row, dict) for row in rows)):
            errors.append(f"step {step_index}: aggregate or consumer row count/shape failed")
            continue
        tags = [row.get("case") for row in rows]
        if any(not isinstance(tag, str) for tag in tags) or sorted(tags) != sorted(wanted):
            errors.append(f"step {step_index}: missing, duplicate or unexpected consumer rows")
            continue
        for row in rows:
            passed = row.get("runtime") == "PASS"
            checks.append({"step": step_index, "bot": bot, "case": row["case"], "passed": passed})
            if not passed:
                errors.append(f"step {step_index}: consumer {row['case']} did not pass")
    return {"valid": not errors, "errors": errors, "checks": checks}
