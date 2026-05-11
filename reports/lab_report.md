# Day 08 Lab Report — Metrics Summary

## Results

| Scenario | Expected | Actual | Success | Retries | Interrupts |
|---|---|---|---:|---:|---:|
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
| S12_persistent_error | error | error | ✅ | 2 | 0 |
| S13_vague_missing | missing_info | missing_info | ✅ | 0 | 0 |
| S14_delete_data | risky | risky | ✅ | 0 | 1 |
| S15_service_down | error | error | ✅ | 2 | 0 |
| S16_retry_dead | error | error | ✅ | 2 | 0 |
| S17_instant_dead | error | error | ✅ | 1 | 0 |
| S18_api_dead | error | error | ✅ | 2 | 0 |

## Aggregate

- **Total scenarios:** 18
- **Success rate:** 100.00%
- **Average nodes visited:** 6.67
- **Total retries:** 12
- **Total interrupts:** 4

---
*For full report with architecture, state schema, failure analysis, and improvement
plan, see reports/lab_report.md*
