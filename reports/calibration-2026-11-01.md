# Calibration report -- 2026-11-01

## Summary

- Fitted on **n=1478** pairs.
- ECE: **0.069 -> 0.011** (+5.8pp on the training set)
- Brier: **0.201 -> 0.196** (+0.005)
- Source: `/home/runner/work/sre-agent/sre-agent/.feedback-ci`

## Reliability diagram (before)

| bin           |   N | mean_pred | frac_correct | gap |
|---------------|-----|-----------|--------------|-----|
| [0.00, 0.10) |   0 |       --- |          --- |  -- |
| [0.10, 0.20) |   0 |       --- |          --- |  -- |
| [0.20, 0.30) |   0 |       --- |          --- |  -- |
| [0.30, 0.40) |   0 |       --- |          --- |  -- |
| [0.40, 0.50) |   0 |       --- |          --- |  -- |
| [0.50, 0.60) |  76 |     0.579 |        0.697 | -11.8pp |
| [0.60, 0.70) | 321 |     0.669 |        0.710 | -4.2pp |
| [0.70, 0.80) | 444 |     0.749 |        0.718 | +3.1pp |
| [0.80, 0.90) | 453 |     0.842 |        0.744 | +9.8pp |
| [0.90, 1.00) | 184 |     0.921 |        0.804 | +11.7pp |

## Reliability diagram (after applying fitted calibrator)

| bin           |   N | mean_pred | frac_correct | gap |
|---------------|-----|-----------|--------------|-----|
| [0.00, 0.10) |   4 |     0.000 |        0.500 | -50.0pp |
| [0.10, 0.20) |   0 |       --- |          --- |  -- |
| [0.20, 0.30) |   0 |       --- |          --- |  -- |
| [0.30, 0.40) |   0 |       --- |          --- |  -- |
| [0.40, 0.50) |  14 |     0.500 |        0.786 | -28.6pp |
| [0.50, 0.60) |   0 |       --- |          --- |  -- |
| [0.60, 0.70) | 187 |     0.694 |        0.706 | -1.2pp |
| [0.70, 0.80) | 1127 |     0.733 |        0.730 | +0.3pp |
| [0.80, 0.90) | 131 |     0.826 |        0.802 | +2.5pp |
| [0.90, 1.00) |  15 |     0.915 |        0.800 | +11.5pp |

## Fitted breakpoints

```
raw=0.550  ->  calibrated=0.000
raw=0.564  ->  calibrated=0.679
raw=0.581  ->  calibrated=0.688
raw=0.591  ->  calibrated=0.688
raw=0.720  ->  calibrated=0.710
raw=0.833  ->  calibrated=0.747
raw=0.871  ->  calibrated=0.764
raw=0.904  ->  calibrated=0.801
raw=0.934  ->  calibrated=0.829
raw=0.952  ->  calibrated=0.923
```

## Decision

- **Propose update?** `True`
- Current live ECE: `0.069`
- New candidate ECE: `0.011`
- ECE drop: `+0.058` (threshold for propose: `0.030`)
- Reason: new ECE 0.011 beats current 0.069 by +0.058
