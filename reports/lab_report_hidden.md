# Day 08 Lab Report — Metrics Summary

## Results

| Scenario | Expected | Actual | Success | Retries | Interrupts |
|---|---|---|---:|---:|---:|
| G01_simple | simple | simple | ✅ | 0 | 0 |
| G02_simple2 | simple | simple | ✅ | 0 | 0 |
| G03_tool | tool | tool | ✅ | 0 | 0 |
| G04_tool2 | tool | tool | ✅ | 0 | 0 |
| G05_tool3 | tool | tool | ✅ | 0 | 0 |
| G06_missing | missing_info | missing_info | ✅ | 0 | 0 |
| G07_missing2 | missing_info | missing_info | ✅ | 0 | 0 |
| G08_risky | risky | risky | ✅ | 0 | 1 |
| G09_risky2 | risky | risky | ✅ | 0 | 1 |
| G10_risky3 | risky | risky | ✅ | 0 | 1 |
| G11_risky4 | risky | risky | ✅ | 0 | 1 |
| G12_error | error | error | ✅ | 2 | 0 |
| G13_error2 | error | error | ✅ | 2 | 0 |
| G14_dead | error | error | ✅ | 1 | 0 |
| G15_mixed | risky | risky | ✅ | 0 | 1 |

## Aggregate

- **Total scenarios:** 15
- **Success rate:** 100.00%
- **Average nodes visited:** 6.60
- **Total retries:** 5
- **Total interrupts:** 5

---
*For full report with architecture, state schema, failure analysis, and improvement
plan, see reports/lab_report.md*
