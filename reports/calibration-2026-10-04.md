# Calibration report -- 2026-10-04

## Summary

- Fitted on **n=1472** pairs.
- ECE: **0.063 -> 0.008** (+5.5pp on the training set)
- Brier: **0.191 -> 0.186** (+0.005)
- Source: `/home/runner/work/sre-agent/sre-agent/.feedback-ci`

## Reliability diagram (before)

| bin           |   N | mean_pred | frac_correct | gap |
|---------------|-----|-----------|--------------|-----|
| [0.00, 0.10) |   0 |       --- |          --- |  -- |
| [0.10, 0.20) |   0 |       --- |          --- |  -- |
| [0.20, 0.30) |   0 |       --- |          --- |  -- |
| [0.30, 0.40) |   0 |       --- |          --- |  -- |
| [0.40, 0.50) |   0 |       --- |          --- |  -- |
| [0.50, 0.60) |  77 |     0.581 |        0.740 | -16.0pp |
| [0.60, 0.70) | 321 |     0.668 |        0.729 | -6.1pp |
| [0.70, 0.80) | 445 |     0.750 |        0.719 | +3.0pp |
| [0.80, 0.90) | 441 |     0.843 |        0.789 | +5.4pp |
| [0.90, 1.00) | 188 |     0.920 |        0.793 | +12.7pp |

## Reliability diagram (after applying fitted calibrator)

| bin           |   N | mean_pred | frac_correct | gap |
|---------------|-----|-----------|--------------|-----|
| [0.00, 0.10) |   0 |       --- |          --- |  -- |
| [0.10, 0.20) |   0 |       --- |          --- |  -- |
| [0.20, 0.30) |   0 |       --- |          --- |  -- |
| [0.30, 0.40) |   3 |     0.333 |        0.333 | +0.0pp |
| [0.40, 0.50) |   0 |       --- |          --- |  -- |
| [0.50, 0.60) |  12 |     0.538 |        0.833 | -29.6pp |
| [0.60, 0.70) |   0 |       --- |          --- |  -- |
| [0.70, 0.80) | 1181 |     0.740 |        0.742 | -0.2pp |
| [0.80, 0.90) | 260 |     0.811 |        0.804 | +0.7pp |
| [0.90, 1.00) |  16 |     1.000 |        0.750 | +25.0pp |

## Fitted breakpoints

```
raw=0.550  ->  calibrated=0.333
raw=0.568  ->  calibrated=0.706
raw=0.642  ->  calibrated=0.719
raw=0.723  ->  calibrated=0.723
raw=0.786  ->  calibrated=0.731
raw=0.834  ->  calibrated=0.790
raw=0.896  ->  calibrated=0.806
raw=0.937  ->  calibrated=0.811
raw=0.950  ->  calibrated=1.000
```

## Decision

- **Propose update?** `True`
- Current live ECE: `0.063`
- New candidate ECE: `0.008`
- ECE drop: `+0.055` (threshold for propose: `0.030`)
- Reason: new ECE 0.008 beats current 0.063 by +0.055
