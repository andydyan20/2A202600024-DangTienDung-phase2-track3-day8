# Day 08 Lab Report — LangGraph Agentic Orchestration

## Architecture

### State Schema
The `AgentState` uses `Annotated` reducers for append-only list fields:
- `messages`: `Annotated[list, add]` - conversation history
- `events`: `Annotated[list, add]` - audit trail
- `tool_results`: `Annotated[list, add]` - tool execution results
- `errors`: `Annotated[list, add]` - error accumulation

Key typed fields include `route` (Route enum), `risk_level`, `attempt`, `max_attempts`, `approval`, and `scenario_id`.

### Graph Flow
```
START → intake → classify → [conditional routing]
```

| Route | Path |
|---|---|
| `simple` | intake → classify → answer → finalize → END |
| `tool` | intake → classify → tool → evaluate → answer → finalize → END |
| `missing_info` | intake → classify → clarify → finalize → END |
| `risky` | intake → classify → risky_action → approval → tool → evaluate → answer → finalize → END |
| `error` | intake → classify → retry → tool → evaluate → (loop or dead_letter) → finalize → END |

### Keyword Priority (highest to lowest)
1. **Risky**: refund, delete, cancel, remove, revoke, terminate, erase, destroy, send
2. **Error**: timeout, fail, failure, crash, unavailable, down, corruption, exhausted, permanently, unrecoverable, outage
3. **Tool**: status, order, lookup, fetch, find, search, check
4. **Missing_info**: short queries (≤5 words) with vague keywords (it, fix, issue, problem, help, broken, thing, something)
5. **Simple**: default fallback

## Metrics Summary

### Grade Scenarios (18 total, 100% success)

| Scenario | Expected | Actual | Success | Retries | Interrupts |
|---|---|---|---|---|---|
| S01_simple | simple | simple | ✅ | 0 | 0 |
| S02_tool | tool | tool | ✅ | 0 | 0 |
| S03_missing | missing_info | missing_info | ✅ | 0 | 0 |
| S04_risky | risky | risky | ✅ | 0 | 1 |
| S05_error | error | error | ✅ | 2 | 0 |
| S06_delete | risky | risky | ✅ | 0 | 1 |
| S07_dead_letter | error | error | ✅ | 1 | 0 |
| S08_pii | simple | simple | ✅ | 0 | 0 |
| S09_urgent | simple | simple | ✅ | 0 | 0 |
| S10_bulk_order | tool | tool | ✅ | 0 | 0 |
| S11_cancel | risky | risky | ✅ | 0 | 1 |
| S12_persistent_error | error | error | ✅ | 3 | 0 |
| S13_vague_missing | missing_info | missing_info | ✅ | 0 | 0 |
| S14_delete_data | risky | risky | ✅ | 0 | 1 |
| S15_service_down | error | error | ✅ | 2 | 0 |
| S16_retry_dead | error | error | ✅ | 2 | 0 |
| S17_instant_dead | error | error | ✅ | 1 | 0 |
| S18_api_dead | error | error | ✅ | 2 | 0 |

### Hidden Scenarios (15 total, 100% success)

| Scenario | Query | Expected | Actual | Success | Retries | Interrupts |
|---|---|---|---|---|---|---|
| G01_simple | What are your business hours? | simple | simple | ✅ | 0 | 0 |
| G02_simple2 | What is your return policy? | simple | simple | ✅ | 0 | 0 |
| G03_tool | Track my shipment for order 7890 | tool | tool | ✅ | 0 | 0 |
| G04_tool2 | Search for invoice number INV-2024-001 | tool | tool | ✅ | 0 | 0 |
| G05_tool3 | Find all pending tickets for account A-555 | tool | tool | ✅ | 0 | 0 |
| G06_missing | Please handle it | missing_info | missing_info | ✅ | 0 | 0 |
| G07_missing2 | Fix it now | missing_info | missing_info | ✅ | 0 | 0 |
| G08_risky | Cancel all pending orders for this customer | risky | risky | ✅ | 0 | 1 |
| G09_risky2 | Remove user profile and all associated data | risky | risky | ✅ | 0 | 1 |
| G10_risky3 | Revoke API access tokens for team workspace | risky | risky | ✅ | 0 | 1 |
| G11_risky4 | Send bulk notification to all premium users | risky | risky | ✅ | 0 | 1 |
| G12_error | Service unavailable when connecting to payment gateway | error | error | ✅ | 2 | 0 |
| G13_error2 | Request failed with internal server error | error | error | ✅ | 2 | 0 |
| G14_dead | Critical crash in authentication module unrecoverable | error | error | ✅ | 1 | 0 |
| G15_mixed | Check refund status for order 456 | risky | risky | ✅ | 0 | 1 |

### Aggregate Metrics
**Grade Scenarios (18):**
- Total scenarios: 18
- Success rate: 100%
- Average nodes visited: 6.83
- Total retries: 13
- Total interrupts: 4 (HITL approval events)

**Hidden Scenarios (15):**
- Total scenarios: 15
- Success rate: 100%
- Average nodes visited: 6.6
- Total retries: 5
- Total interrupts: 5

## Failure Analysis

### Error Route Scenarios
The error scenarios (S05, S07, S12, S15, S16, S17, S18) correctly trigger the retry mechanism:
- **S05_error**: 2 retries with exponential backoff (2s, 4s) before success
- **S07_dead_letter**: Limited to 1 max attempt, correctly routes to dead_letter
- **S12_persistent_error**: 3 retries with backoff (2s, 4s, 8s) before success
- **S17_instant_dead** / **S16_retry_dead**: Demonstrate bounded retry exhaustion

### Retry Logic
The `evaluate_node` checks for error indicators in tool results:
- `"ERROR"` in result string
- `'status': 'error'` in JSON
- Error keywords in first 40 characters

When `evaluation_result = "needs_retry"`, the `route_after_retry` function decides whether to loop back to tool or route to dead_letter.

### Dead Letter Handling
The `dead_letter_node` emits a structured record with:
- Scenario ID
- Final attempt number
- Error count and messages
- Status marker for manual review

## Bonus Extensions

### 1. Crash Recovery & Persistence
- MemorySaver checkpointer with thread_id per run
- SQLite backend support with WAL mode
- State recovery verified via `get_state()` after simulated crash

### 2. Time Travel
- `get_state_history()` retrieves checkpoint snapshots
- Replay capability demonstrated with `graph.invoke(state, config)` from historical state
- Verification: replayed answer matches original

### 3. Parallel Fan-out via Send()
- Uses LangGraph `Send` API for concurrent tool execution
- Merges results via `Annotated[list, add]` reducer
- Pattern: parallel workers → result aggregation → single answer

### 4. HITL Approval UI (Streamlit)
- `LANGGRAPH_INTERRUPT=true` enables real `interrupt()` calls
- Approval panel with approve/reject/edit options
- Auto-approval in batch mode for testing

### 5. Graph Diagram (Mermaid)
- Auto-generated via `graph.get_graph().draw_mermaid()`
- Stored in `outputs/graph_diagram.md`

## Improvements & Future Work

1. **Real Tool Integration**: Replace mock tool with actual API calls (database queries, email service, payment gateway)

2. **Enhanced Classification**: Train a small classifier on query embeddings for more robust routing vs. keyword matching

3. **Dynamic Retry Policy**: Use exponential backoff with jitter; add circuit breaker pattern for repeated failures

4. **Extended PII Support**: Add detection for SSN, passport numbers, bank accounts

5. **Approval Audit Trail**: Store approval decisions in database with full context for compliance

6. **Rate Limiting**: Add token bucket rate limiter for tool calls to prevent avalanche

7. **Observability**: Export traces to OpenTelemetry for production monitoring

## Quick Commands

```bash
# Run all scenarios
make run-scenarios

# Validate metrics
make grade-local

# Run hidden scenarios
make run-hidden

# Launch HITL UI
make hitl

# Run extensions demo
make extensions
```

## Submission Checklist
- [x] All TODO(student) sections completed
- [x] `make test` passes
- [x] `make run-scenarios` generates valid `outputs/metrics.json`
- [x] `make grade-local` passes validation
- [x] Reports written with architecture, metrics, failures, improvements
- [x] Bonus extensions implemented (persistence, parallel fan-out, HITL, time travel, diagram)
- [x] Evidence included in report