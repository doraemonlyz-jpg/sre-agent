# Calibration report -- 2026-06-07

## Summary

- Fitted on **n=1472** pairs.
- ECE: **0.056 -> 0.007** (+5.0pp on the training set)
- Brier: **0.199 -> 0.194** (+0.005)
- Source: `/home/runner/work/sre-agent/sre-agent/.feedback-ci`

## Reliability diagram (before)

| bin           |   N | mean_pred | frac_correct | gap |
|---------------|-----|-----------|--------------|-----|
| [0.00, 0.10) |   0 |       --- |          --- |  -- |
| [0.10, 0.20) |   0 |       --- |          --- |  -- |
| [0.20, 0.30) |   0 |       --- |          --- |  -- |
| [0.30, 0.40) |   0 |       --- |          --- |  -- |
| [0.40, 0.50) |   0 |       --- |          --- |  -- |
| [0.50, 0.60) |  71 |     0.577 |        0.690 | -11.3pp |
| [0.60, 0.70) | 330 |     0.668 |        0.691 | -2.2pp |
| [0.70, 0.80) | 452 |     0.750 |        0.730 | +2.0pp |
| [0.80, 0.90) | 440 |     0.842 |        0.775 | +6.7pp |
| [0.90, 1.00) | 179 |     0.922 |        0.760 | +16.2pp |

## Reliability diagram (after applying fitted calibrator)

| bin           |   N | mean_pred | frac_correct | gap |
|---------------|-----|-----------|--------------|-----|
| [0.00, 0.10) |   0 |       --- |          --- |  -- |
| [0.10, 0.20) |   0 |       --- |          --- |  -- |
| [0.20, 0.30) |   0 |       --- |          --- |  -- |
| [0.30, 0.40) |   6 |     0.333 |        0.667 | -33.3pp |
| [0.40, 0.50) |   0 |       --- |          --- |  -- |
| [0.50, 0.60) |   0 |       --- |          --- |  -- |
| [0.60, 0.70) | 297 |     0.688 |        0.697 | -0.9pp |
| [0.70, 0.80) | 1060 |     0.742 |        0.743 | -0.1pp |
| [0.80, 0.90) | 109 |     0.818 |        0.780 | +3.9pp |
| [0.90, 1.00) |   0 |       --- |          --- |  -- |

## Fitted breakpoints

```
raw=0.550  ->  calibrated=0.333
raw=0.555  ->  calibrated=0.667
raw=0.626  ->  calibrated=0.685
raw=0.685  ->  calibrated=0.699
raw=0.754  ->  calibrated=0.725
raw=0.810  ->  calibrated=0.746
raw=0.865  ->  calibrated=0.775
raw=0.920  ->  calibrated=0.800
raw=0.934  ->  calibrated=0.829
raw=0.952  ->  calibrated=0.833
```

## Decision

- **Propose update?** `True`
- Current live ECE: `0.056`
- New candidate ECE: `0.007`
- ECE drop: `+0.050` (threshold for propose: `0.030`)
- Reason: new ECE 0.007 beats current 0.056 by +0.050
