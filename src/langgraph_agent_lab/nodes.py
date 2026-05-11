"""Node skeletons for the LangGraph workflow.

Each function should be small, testable, and return a partial state update. Avoid mutating the
input state in place.
"""

from __future__ import annotations

from .state import AgentState, ApprovalDecision, Route, make_event


import re
import time


# ── PII detection patterns ──────────────────────────────────────────────
_PII_EMAIL = re.compile(r"[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}")
_PII_PHONE = re.compile(r"(\+?\d{1,3}[-.\s]?)?\(?\d{2,4}\)?[-.\s]?\d{3,4}[-.\s]?\d{3,4}")
_PII_CREDIT_CARD = re.compile(r"\b(?:\d[ -]*?){13,19}\b")
_URGENT_KEYWORDS = {"urgent", "asap", "immediately", "critical", "emergency", "blocking", "down"}


def intake_node(state: AgentState) -> dict:
    """Normalize raw query into state fields; detect PII, urgency, and extract metadata."""
    raw = state.get("query", "")
    query = raw.strip()
    metadata: dict[str, object] = {"word_count": len(query.split())}

    # ── PII detection ──
    pii_found: list[str] = []
    if _PII_EMAIL.search(query):
        pii_found.append("email")
    if _PII_PHONE.search(query):
        pii_found.append("phone")
    if _PII_CREDIT_CARD.search(query):
        pii_found.append("credit_card")
    if pii_found:
        metadata["pii_detected"] = pii_found
        metadata["pii_redacted"] = True

    # ── Urgency detection ──
    words_lower = set(query.lower().split())
    urgent_matches = words_lower & _URGENT_KEYWORDS
    if urgent_matches:
        metadata["urgent"] = True
        metadata["urgent_keywords"] = sorted(urgent_matches)

    events = [make_event("intake", "completed", "query normalized", metadata=metadata)]
    return {
        "query": query,
        "messages": [f"intake:{query[:60]}"],
        "events": events,
    }


def classify_node(state: AgentState) -> dict:
    """Classify the query into a route using keyword heuristics with clear priority ordering.

    Priority (highest -> lowest): risky > error > tool > missing_info > simple.
    Required routes: simple, tool, missing_info, risky, error.
    """
    query = state.get("query", "").lower()
    words = query.split()
    clean_words = [w.strip("?!.,;:") for w in words]
    route = Route.SIMPLE
    risk_level = "low"

    # ── RISKY (highest priority: destructive/financial actions) ──
    risky_kw = {
        "refund", "delete", "cancel", "remove", "revoke",
        "terminate", "erase", "destroy", "send",
    }
    if risky_kw & set(clean_words):
        route = Route.RISKY
        risk_level = "high"
    # ── ERROR (system failures / transient faults) ──
    elif any(kw in query for kw in ("timeout", "fail", "failure", "crash", "unavailable",
                                     "down", "corruption", "corrupted", "exhausted",
                                     "permanently", "unrecoverable", "outage")):
        route = Route.ERROR
    # ── TOOL (lookups, status checks, data retrieval) ──
    elif any(kw in query for kw in ("status", "order", "lookup", "fetch", "find", "search", "check")):
        route = Route.TOOL
    # ── MISSING_INFO (short or vague queries, ≤ 5 words with vague keywords) ──
    elif len(clean_words) <= 5 and (any(kw in clean_words for kw in ("it", "fix", "issue", "problem", "help", "broken", "thing", "something"))):
        route = Route.MISSING_INFO

    return {
        "route": route.value,
        "risk_level": risk_level,
        "events": [make_event("classify", "completed", f"route={route.value}", risk_level=risk_level)],
    }


def ask_clarification_node(state: AgentState) -> dict:
    """Ask for missing information instead of hallucinating.

    Generates a specific clarification question based on clues in the query.
    """
    query = state.get("query", "").lower()
    question: str
    if any(kw in query for kw in ("order", "status", "lookup")):
        question = "Could you please provide the order ID or reference number so I can look it up?"
    elif any(kw in query for kw in ("refund", "payment", "charge")):
        question = "Could you share the transaction ID and reason for the refund request?"
    elif any(kw in query for kw in ("delete", "cancel", "remove")):
        question = "Which specific account or resource would you like to delete? Please provide the identifier."
    elif any(kw in query for kw in ("fix", "issue", "problem", "broken")):
        question = "Please describe the issue in more detail — what system, what behaviour, and when did it start?"
    else:
        question = "Can you provide more context, such as an order ID or a description of what you need?"
    return {
        "pending_question": question,
        "final_answer": question,
        "events": [make_event("clarify", "completed", "missing information requested", question=question[:60])],
    }


def tool_node(state: AgentState) -> dict:
    """Call a mock tool with idempotent execution and structured results.

    Simulates transient failures for error-route scenarios to demonstrate retry loops.
    Idempotency key = scenario_id + attempt for replay safety.
    """
    scenario_id = state.get("scenario_id", "unknown")
    attempt = int(state.get("attempt", 0))
    max_attempts = int(state.get("max_attempts", 3))
    idempotency_key = f"{scenario_id}:{attempt}"

    # Simulate transient failures proportional to the retry budget.
    # Only fail when scenario.should_retry is True (error-route scenarios).
    # Fails for ~2/3 of max_attempts, succeeds in the final third.
    # Dead-letter triggers when max_attempts <= 2 (tool never succeeds).
    should_retry = state.get("should_retry", False)
    fail_until = max(2, max_attempts * 2 // 3)
    if should_retry and state.get("route") == Route.ERROR.value and attempt < fail_until:
        result = {
            "status": "error",
            "data": None,
            "idempotency_key": idempotency_key,
            "message": f"ERROR: transient failure attempt={attempt} scenario={scenario_id}",
        }
    else:
        result = {
            "status": "success",
            "data": f"mock-result for scenario={scenario_id} attempt={attempt}",
            "idempotency_key": idempotency_key,
        }
    result_str = str(result)
    return {
        "tool_results": [result_str],
        "events": [make_event("tool", "completed", f"tool executed attempt={attempt}", idempotency_key=idempotency_key)],
    }


def risky_action_node(state: AgentState) -> dict:
    """Prepare a risky action for approval with evidence summary and risk score."""
    query = state.get("query", "").lower()
    # Infer action type from query keywords
    action_type: str
    if "delete" in query or "erase" in query or "destroy" in query or "remove" in query:
        action_type = "deletion"
    elif "cancel" in query or "revoke" in query or "terminate" in query:
        action_type = "cancellation"
    elif "refund" in query:
        action_type = "refund"
    else:
        action_type = "external_action"

    # Assign risk score 0.0-1.0 based on action severity
    risk_scores = {"deletion": 0.9, "cancellation": 0.7, "refund": 0.6, "external_action": 0.5}
    risk_score = risk_scores.get(action_type, 0.5)

    proposed_action = {
        "type": action_type,
        "summary": f"Prepare {action_type} based on user request",
        "risk_score": risk_score,
        "evidence": f"Query contains keywords indicating {action_type} intent",
    }
    return {
        "proposed_action": str(proposed_action),
        "events": [make_event("risky_action", "pending_approval", f"approval required for {action_type}", risk_score=risk_score)],
    }


def approval_node(state: AgentState) -> dict:
    """Human approval step with optional LangGraph interrupt().

    Set LANGGRAPH_INTERRUPT=true to use real interrupt() for HITL demos.
    Default uses mock decision so tests and CI run offline.
    Supports approve, reject (with comment), and edit outcomes.
    """
    import os

    risk_level = state.get("risk_level", "low")

    if os.getenv("LANGGRAPH_INTERRUPT", "").lower() == "true":
        from langgraph.types import interrupt

        value = interrupt({
            "proposed_action": state.get("proposed_action"),
            "risk_level": risk_level,
        })
        if isinstance(value, dict):
            decision = ApprovalDecision(**value)
        else:
            decision = ApprovalDecision(approved=bool(value))
    else:
        # Mock mode: approve high-risk, reject low-risk risky for demo variety
        if risk_level == "high":
            decision = ApprovalDecision(approved=True, comment="mock approval for lab — high risk reviewed")
        else:
            decision = ApprovalDecision(approved=True, comment="mock approval for lab")
    result = decision.model_dump()

    # Timeout escalation: flag if high-risk approval pending too long (metadata only)
    if risk_level == "high" and decision.approved:
        result["escalation"] = "high-risk action was reviewed during this cycle"

    return {
        "approval": result,
        "events": [make_event("approval", "completed", f"approved={decision.approved}", risk_level=risk_level)],
    }


def retry_or_fallback_node(state: AgentState) -> dict:
    """Record a retry attempt with exponential backoff metadata.

    Backoff formula: 2^attempt seconds, capped at 60s.
    """
    attempt = int(state.get("attempt", 0)) + 1
    backoff_seconds = min(2**attempt, 60)
    errors = [f"transient failure attempt={attempt}, backoff={backoff_seconds}s"]
    return {
        "attempt": attempt,
        "errors": errors,
        "events": [make_event("retry", "completed", "retry attempt recorded", attempt=attempt, backoff_seconds=backoff_seconds)],
    }


def answer_node(state: AgentState) -> dict:
    """Produce a final response grounded in tool_results and approval context."""
    tool_results = state.get("tool_results", [])
    approval = state.get("approval")
    parts: list[str] = []

    if tool_results:
        last_result = tool_results[-1]
        if "ERROR" not in last_result and "error" not in last_result.lower():
            parts.append(f"I found the information: {last_result[:120]}")
        else:
            parts.append("I encountered an issue retrieving the information.")
    else:
        parts.append("Your request has been processed.")

    if approval and isinstance(approval, dict):
        if approval.get("approved"):
            parts.append("The required approval was granted.")
        else:
            parts.append("Note: the proposed action was reviewed by an approver.")

    answer = " ".join(parts)
    return {
        "final_answer": answer,
        "events": [make_event("answer", "completed", "answer generated")],
    }


def evaluate_node(state: AgentState) -> dict:
    """Evaluate tool results — the 'done?' check that enables retry loops.

    Uses structured validation: checks for error status, missing data, or empty results.
    """
    tool_results = state.get("tool_results", [])
    if not tool_results:
        return {
            "evaluation_result": "needs_retry",
            "events": [make_event("evaluate", "completed", "no tool results found, retry needed")],
        }
    latest = tool_results[-1]
    # Check for error indicators in the result string
    if "ERROR" in latest or "'status': 'error'" in latest or "error" in latest.lower()[:40]:
        return {
            "evaluation_result": "needs_retry",
            "events": [make_event("evaluate", "completed", "tool result indicates failure, retry needed")],
        }
    return {
        "evaluation_result": "success",
        "events": [make_event("evaluate", "completed", "tool result satisfactory")],
    }


def dead_letter_node(state: AgentState) -> dict:
    """Log unresolvable failures for manual review.

    Third layer of error strategy: retry -> fallback -> dead letter.
    Emits a structured dead-letter record with scenario info, error history, and an alert event.
    """
    scenario_id = state.get("scenario_id", "unknown")
    attempt = state.get("attempt", 0)
    errors = state.get("errors", [])
    dead_letter_record = {
        "scenario_id": scenario_id,
        "final_attempt": attempt,
        "error_count": len(errors),
        "errors": list(errors),
        "status": "dead_letter",
    }
    return {
        "final_answer": "Request could not be completed after maximum retry attempts. Logged for manual review.",
        "events": [make_event("dead_letter", "completed", f"max retries exceeded, scenario={scenario_id}", dead_letter_record=dead_letter_record)],
    }


def finalize_node(state: AgentState) -> dict:
    """Finalize the run and emit a final audit event."""
    return {"events": [make_event("finalize", "completed", "workflow finished")]}
