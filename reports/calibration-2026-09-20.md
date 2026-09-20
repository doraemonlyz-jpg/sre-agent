# Calibration report -- 2026-09-20

## Summary

- Fitted on **n=1424** pairs.
- ECE: **0.065 -> 0.011** (+5.4pp on the training set)
- Brier: **0.205 -> 0.197** (+0.008)
- Source: `/home/runner/work/sre-agent/sre-agent/.feedback-ci`

## Reliability diagram (before)

| bin           |   N | mean_pred | frac_correct | gap |
|---------------|-----|-----------|--------------|-----|
| [0.00, 0.10) |   0 |       --- |          --- |  -- |
| [0.10, 0.20) |   0 |       --- |          --- |  -- |
| [0.20, 0.30) |   0 |       --- |          --- |  -- |
| [0.30, 0.40) |   0 |       --- |          --- |  -- |
| [0.40, 0.50) |   0 |       --- |          --- |  -- |
| [0.50, 0.60) |  71 |     0.582 |        0.606 | -2.4pp |
| [0.60, 0.70) | 309 |     0.667 |        0.706 | -3.9pp |
| [0.70, 0.80) | 424 |     0.750 |        0.726 | +2.3pp |
| [0.80, 0.90) | 443 |     0.842 |        0.761 | +8.1pp |
| [0.90, 1.00) | 177 |     0.923 |        0.740 | +18.3pp |

## Reliability diagram (after applying fitted calibrator)

| bin           |   N | mean_pred | frac_correct | gap |
|---------------|-----|-----------|--------------|-----|
| [0.00, 0.10) |   0 |       --- |          --- |  -- |
| [0.10, 0.20) |   0 |       --- |          --- |  -- |
| [0.20, 0.30) |   0 |       --- |          --- |  -- |
| [0.30, 0.40) |   0 |       --- |          --- |  -- |
| [0.40, 0.50) |   0 |       --- |          --- |  -- |
| [0.50, 0.60) |  36 |     0.557 |        0.583 | -2.6pp |
| [0.60, 0.70) | 132 |     0.675 |        0.727 | -5.3pp |
| [0.70, 0.80) | 1256 |     0.738 |        0.732 | +0.6pp |
| [0.80, 0.90) |   0 |       --- |          --- |  -- |
| [0.90, 1.00) |   0 |       --- |          --- |  -- |

## Fitted breakpoints

```
raw=0.567  ->  calibrated=0.548
raw=0.586  ->  calibrated=0.583
raw=0.595  ->  calibrated=0.625
raw=0.600  ->  calibrated=0.667
raw=0.665  ->  calibrated=0.704
raw=0.758  ->  calibrated=0.722
raw=0.840  ->  calibrated=0.755
raw=0.910  ->  calibrated=0.777
```

## Decision

- **Propose update?** `True`
- Current live ECE: `0.065`
- New candidate ECE: `0.011`
- ECE drop: `+0.054` (threshold for propose: `0.030`)
- Reason: new ECE 0.011 beats current 0.065 by +0.054
