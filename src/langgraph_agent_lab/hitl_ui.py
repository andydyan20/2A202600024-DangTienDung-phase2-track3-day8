"""Streamlit HITL (Human-in-the-Loop) approval UI for the LangGraph agent lab.

Launch with:
    streamlit run src/langgraph_agent_lab/hitl_ui.py

Or via make:
    make hitl

Requires: pip install streamlit
"""

from __future__ import annotations

import json
import os
import sys
import time
from pathlib import Path
from typing import Any

# ── Ensure LANGGRAPH_INTERRUPT is enabled ─────────────────────────────────
os.environ["LANGGRAPH_INTERRUPT"] = "true"

# Add project root to path so the package can be imported
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

import streamlit as st  # noqa: E402
from langgraph.types import Command  # noqa: E402

from langgraph_agent_lab.graph import build_graph  # noqa: E402
from langgraph_agent_lab.persistence import build_checkpointer  # noqa: E402
from langgraph_agent_lab.scenarios import Scenario  # noqa: E402
from langgraph_agent_lab.state import initial_state  # noqa: E402

# ── Page setup ──────────────────────────────────────────────────────────────
st.set_page_config(page_title="HITL Agent Approval", page_icon="🛡️", layout="wide")
st.title("🛡️ Human-in-the-Loop — Agent Approval Dashboard")
st.caption("LangGraph Agent Lab · Day 08 · Phase 2 Track 3")

# ── Sidebar: quick scenarios ────────────────────────────────────────────────
HITL_PRESETS: dict[str, str] = {
    "Custom query…": "",
    "🟡 Refund + email (medium risk)":
        "Refund this customer and send confirmation email",
    "🟠 Cancel subscription + refund (high risk)":
        "Cancel my premium subscription and refund the last payment",
    "🔴 Delete account (destructive)":
        "Delete customer account after support verification",
    "🔴 Delete all data — GDPR (destructive)":
        "Delete all my stored payment methods and transaction history",
    "🟡 Refund single order with reason":
        "Please refund order #98765 — item arrived damaged",
    "🟠 Terminate service + reverse charges":
        "Terminate the business account and reverse all pending charges",
    "🔴 Wipe user data under compliance request":
        "Permanently erase user profile and all records per GDPR article 17",
    "🟡 Grant admin access to external auditor":
        "Grant temporary admin access to auditor@firm.com for compliance review",
}

with st.sidebar:
    st.header("⚡ Quick Scenario")
    preset = st.selectbox(
        "Preset risky scenarios (all require HITL approval)",
        list(HITL_PRESETS.keys()),
    )
    query = st.text_area(
        "User query",
        value=HITL_PRESETS[preset],
        height=100,
        placeholder="e.g. Refund this customer and send confirmation email",
    )
    max_attempts = st.slider("Max retry attempts", 1, 5, 3)

    col_a, col_b = st.columns(2)
    with col_a:
        run_btn = st.button("▶️ Run Agent", type="primary", use_container_width=True)
    with col_b:
        batch_btn = st.button("🧪 Batch Test All", use_container_width=True)

# ── Main area: Results ──────────────────────────────────────────────────────
col1, col2 = st.columns([3, 2])

with col1:
    st.subheader("📋 Agent Workflow")
    log_container = st.container(height=400)

with col2:
    st.subheader("🛡️ Approval Panel")
    approval_container = st.container()

# ── Core logic ──────────────────────────────────────────────────────────────

if "agent_state" not in st.session_state:
    st.session_state.agent_state = None
if "approval_pending" not in st.session_state:
    st.session_state.approval_pending = False
if "interrupt_data" not in st.session_state:
    st.session_state.interrupt_data = None
if "thread_id" not in st.session_state:
    st.session_state.thread_id = None
if "graph" not in st.session_state:
    checkpointer = build_checkpointer("memory")
    st.session_state.graph = build_graph(checkpointer=checkpointer)


def build_scenario(query_text: str) -> Scenario:
    """Build a Scenario from the UI query."""
    q = query_text.lower()
    if any(kw in q for kw in ("refund", "delete", "cancel", "remove", "revoke")):
        route = "risky"
    else:
        route = "simple"
    return Scenario(
        id=f"hitl-{int(time.time())}",
        query=query_text,
        expected_route=route,  # type: ignore[arg-type]
        requires_approval=True,
        max_attempts=max_attempts,
        tags=["hitl", "interactive"],
    )


def run_agent():
    """Run the agent up to the interrupt point.

    Uses invoke() so that interrupt() raises GraphInterrupt, which we catch
    to show the approval panel. Falls back to stream for normal flows.
    """
    scenario = build_scenario(query)
    state = initial_state(scenario)
    thread_id = state["thread_id"]
    st.session_state.thread_id = thread_id
    config = {"configurable": {"thread_id": thread_id}}

    log_container.info(f"**Thread:** `{thread_id}`")
    log_container.info(f"**Query:** {query}")

    graph = st.session_state.graph

    # Stream to show node progress, then check for interrupt
    last_node = ""
    try:
        for event in graph.stream(state, config, stream_mode="updates"):
            for node_name, node_data in event.items():
                last_node = node_name
                route = node_data.get("route", "") if isinstance(node_data, dict) else ""
                risk = node_data.get("risk_level", "") if isinstance(node_data, dict) else ""
                answer = node_data.get("final_answer") if isinstance(node_data, dict) else None
                pending = node_data.get("pending_question") if isinstance(node_data, dict) else None
                proposed = node_data.get("proposed_action") if isinstance(node_data, dict) else None
                errors_list = node_data.get("errors", []) if isinstance(node_data, dict) else []

                emoji = {"intake": "📥", "classify": "🔍", "tool": "🔧", "evaluate": "✅",
                         "retry": "🔄", "dead_letter": "💀", "risky_action": "⚠️",
                         "approval": "🛡️", "clarify": "❓", "answer": "💬",
                         "finalize": "🏁"}.get(node_name, "•")

                log_container.write(f"{emoji} `{node_name}`")
                if route:
                    log_container.caption(f"  ↳ Route: `{route}` | Risk: `{risk}`")
                if proposed:
                    log_container.warning(f"  ⚠️ Proposed: {str(proposed)[:200]}")
                if answer:
                    log_container.success(f"  💬 Answer: {answer}")
                if pending:
                    log_container.info(f"  ❓ Pending question: {pending}")
                if errors_list:
                    for e in errors_list:
                        log_container.error(f"  ❌ {e}")

        # Stream completed — check if graph was interrupted at approval
        current_state = graph.get_state(config)
        if current_state and current_state.next:
            next_nodes = tuple(current_state.next)
            if "approval" in next_nodes:
                st.session_state.approval_pending = True
                st.rerun()
            elif answer:
                log_container.success(f"💬 **Final answer:** {answer}")

    except Exception as exc:
        err_type = type(exc).__name__
        err_msg = str(exc)
        if "GraphInterrupt" in err_type or "interrupt" in err_msg.lower():
            st.session_state.approval_pending = True
            st.rerun()
        else:
            log_container.error(f"Agent error ({err_type}): {err_msg}")


# ── Run button handler ──────────────────────────────────────────────────────
if run_btn:
    if not query.strip():
        st.error("Please enter a query")
    else:
        st.session_state.approval_pending = False
        st.session_state.interrupt_data = None
        log_container.empty()
        with log_container:
            run_agent()

# ── Batch test: run all HITL presets and show summary ───────────────────────
if batch_btn:
    st.session_state.approval_pending = False
    st.session_state.batch_results = []
    log_container.empty()
    approval_container.empty()

    with log_container:
        st.info("🧪 **Batch HITL Test** — running all presets…")
        for label, q in HITL_PRESETS.items():
            if not q or label == "Custom query…":
                continue
            st.divider()
            st.write(f"### {label}")
            st.code(q)

            scenario = build_scenario(q)
            state = initial_state(scenario)
            thread_id = state["thread_id"]
            config = {"configurable": {"thread_id": thread_id}}
            graph = st.session_state.graph

            try:
                for event in graph.stream(state, config, stream_mode="values"):
                    pass  # let graph run — interrupt will be caught
            except Exception as exc:
                err = str(exc)
                if "interrupt" in err.lower():
                    # Auto-approve in batch mode
                    try:
                        for ev in graph.stream(
                            Command(resume={"approved": True, "reviewer": "batch-test", "comment": "Auto-approved in batch"}),
                            config,
                            stream_mode="values",
                        ):
                            node_name = list(ev.keys())[0] if isinstance(ev, dict) else "?"
                            nd = ev[node_name] if isinstance(ev, dict) and node_name in ev else {}
                            if isinstance(nd, dict) and nd.get("final_answer"):
                                st.success(f"✅ Approved → {nd['final_answer'][:120]}")
                    except Exception as e2:
                        st.error(f"Resume failed: {e2}")
                else:
                    st.error(f"Failed: {exc}")
        st.success("🧪 Batch test complete — all presets processed with auto-approval")

# ── Approval panel logic ────────────────────────────────────────────────────
if st.session_state.approval_pending:
    with approval_container:
        st.warning("⚠️ **Action requires human approval**")

        # Show what's being proposed
        st.markdown("### Proposed Action")
        st.code(query, language=None)

        # Risk indicator
        st.progress(0.75, text="Risk Level: HIGH")

        decision = st.radio(
            "Your decision",
            ["✅ Approve", "❌ Reject", "✏️ Edit & Re-evaluate"],
            key="approval_decision",
        )

        comment = st.text_input("Reviewer comment (optional)", key="approval_comment")

        if st.button("Submit Decision", type="primary", use_container_width=True):
            approved = "Approve" in decision
            edited = "Edit" in decision

            decision_dict: dict[str, Any] = {
                "approved": approved,
                "reviewer": "hitl-dashboard",
                "comment": comment or ("Approved" if approved else "Rejected"),
            }
            if edited:
                decision_dict["edited_action"] = True

            # Resume the graph with Command
            graph = st.session_state.graph
            config = {"configurable": {"thread_id": st.session_state.thread_id}}

            try:
                for event in graph.stream(
                    Command(resume=decision_dict), config, stream_mode="updates",
                ):
                    for node_name, node_data in event.items():
                        if isinstance(node_data, dict):
                            answer = node_data.get("final_answer")
                            errors = node_data.get("errors", [])
                            if answer:
                                approval_container.success(f"💬 **Final answer:** {answer}")
                            if errors:
                                for e in errors:
                                    approval_container.error(f"❌ {e}")

                st.session_state.approval_pending = False
                st.balloons()
            except Exception as exc:
                approval_container.error(f"Resume error: {exc}")

# ── Footer ──────────────────────────────────────────────────────────────────
with st.sidebar:
    st.divider()
    st.caption("LangGraph Agent Lab · Day 08")
    st.caption(f"LANGGRAPH_INTERRUPT = {os.getenv('LANGGRAPH_INTERRUPT', 'false')}")
