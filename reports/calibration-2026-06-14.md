# Calibration report -- 2026-06-14

## Summary

- Fitted on **n=1482** pairs.
- ECE: **0.076 -> 0.012** (+6.5pp on the training set)
- Brier: **0.202 -> 0.198** (+0.004)
- Source: `/home/runner/work/sre-agent/sre-agent/.feedback-ci`

## Reliability diagram (before)

| bin           |   N | mean_pred | frac_correct | gap |
|---------------|-----|-----------|--------------|-----|
| [0.00, 0.10) |   0 |       --- |          --- |  -- |
| [0.10, 0.20) |   0 |       --- |          --- |  -- |
| [0.20, 0.30) |   0 |       --- |          --- |  -- |
| [0.30, 0.40) |   0 |       --- |          --- |  -- |
| [0.40, 0.50) |   0 |       --- |          --- |  -- |
| [0.50, 0.60) |  76 |     0.576 |        0.737 | -16.1pp |
| [0.60, 0.70) | 347 |     0.668 |        0.726 | -5.9pp |
| [0.70, 0.80) | 434 |     0.749 |        0.719 | +3.0pp |
| [0.80, 0.90) | 437 |     0.840 |        0.748 | +9.2pp |
| [0.90, 1.00) | 188 |     0.922 |        0.777 | +14.5pp |

## Reliability diagram (after applying fitted calibrator)

| bin           |   N | mean_pred | frac_correct | gap |
|---------------|-----|-----------|--------------|-----|
| [0.00, 0.10) |   8 |     0.000 |        0.875 | -87.5pp |
| [0.10, 0.20) |   0 |       --- |          --- |  -- |
| [0.20, 0.30) |   0 |       --- |          --- |  -- |
| [0.30, 0.40) |   0 |       --- |          --- |  -- |
| [0.40, 0.50) |   0 |       --- |          --- |  -- |
| [0.50, 0.60) |  18 |     0.508 |        0.778 | -26.9pp |
| [0.60, 0.70) |  13 |     0.699 |        0.462 | +23.7pp |
| [0.70, 0.80) | 1443 |     0.737 |        0.739 | -0.2pp |
| [0.80, 0.90) |   0 |       --- |          --- |  -- |
| [0.90, 1.00) |   0 |       --- |          --- |  -- |

## Fitted breakpoints

```
raw=0.550  ->  calibrated=0.000
raw=0.564  ->  calibrated=0.698
raw=0.698  ->  calibrated=0.724
raw=0.784  ->  calibrated=0.726
raw=0.799  ->  calibrated=0.733
raw=0.836  ->  calibrated=0.736
raw=0.880  ->  calibrated=0.750
raw=0.881  ->  calibrated=0.789
raw=0.918  ->  calibrated=0.792
```

## Decision

- **Propose update?** `True`
- Current live ECE: `0.076`
- New candidate ECE: `0.012`
- ECE drop: `+0.065` (threshold for propose: `0.030`)
- Reason: new ECE 0.012 beats current 0.076 by +0.065
