"""Routing functions for conditional edges."""

from __future__ import annotations

from .state import AgentState, Route


def route_after_classify(state: AgentState) -> str:
    """Map classified route to the next graph node.

    Unknown routes safely fall back to 'answer' so the workflow always terminates.
    """
    route = state.get("route", Route.SIMPLE.value)
    mapping = {
        Route.SIMPLE.value: "answer",
        Route.TOOL.value: "tool",
        Route.MISSING_INFO.value: "clarify",
        Route.RISKY.value: "risky_action",
        Route.ERROR.value: "retry",
    }
    return mapping.get(route, "answer")


def route_after_retry(state: AgentState) -> str:
    """Bounded retry: continue retrying until max_attempts, then dead-letter.

    Prevents infinite retry loops — a key LangGraph advantage over LCEL.
    """
    if int(state.get("attempt", 0)) >= int(state.get("max_attempts", 3)):
        return "dead_letter"
    return "tool"


def route_after_evaluate(state: AgentState) -> str:
    """Decide whether tool result is satisfactory or needs retry.

    This is the 'done?' check that enables retry loops — a key LangGraph advantage over LCEL.
    Uses structured validation from evaluate_node to decide success vs. needs_retry.
    """
    if state.get("evaluation_result") == "needs_retry":
        return "retry"
    return "answer"


def route_after_approval(state: AgentState) -> str:
    """Route based on approval outcome: approve → tool, reject → clarify, edit → risky_action."""
    approval = state.get("approval") or {}
    if approval.get("approved"):
        return "tool"
    # If the approval has an edited_action, re-evaluate the risky action
    if approval.get("edited_action"):
        return "risky_action"
    return "clarify"
