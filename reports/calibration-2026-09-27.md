# Calibration report -- 2026-09-27

## Summary

- Fitted on **n=1428** pairs.
- ECE: **0.054 -> 0.011** (+4.3pp on the training set)
- Brier: **0.192 -> 0.187** (+0.004)
- Source: `/home/runner/work/sre-agent/sre-agent/.feedback-ci`

## Reliability diagram (before)

| bin           |   N | mean_pred | frac_correct | gap |
|---------------|-----|-----------|--------------|-----|
| [0.00, 0.10) |   0 |       --- |          --- |  -- |
| [0.10, 0.20) |   0 |       --- |          --- |  -- |
| [0.20, 0.30) |   0 |       --- |          --- |  -- |
| [0.30, 0.40) |   0 |       --- |          --- |  -- |
| [0.40, 0.50) |   0 |       --- |          --- |  -- |
| [0.50, 0.60) |  70 |     0.581 |        0.729 | -14.7pp |
| [0.60, 0.70) | 328 |     0.666 |        0.704 | -3.8pp |
| [0.70, 0.80) | 419 |     0.750 |        0.730 | +1.9pp |
| [0.80, 0.90) | 419 |     0.841 |        0.780 | +6.1pp |
| [0.90, 1.00) | 192 |     0.923 |        0.812 | +11.1pp |

## Reliability diagram (after applying fitted calibrator)

| bin           |   N | mean_pred | frac_correct | gap |
|---------------|-----|-----------|--------------|-----|
| [0.00, 0.10) |   0 |       --- |          --- |  -- |
| [0.10, 0.20) |   0 |       --- |          --- |  -- |
| [0.20, 0.30) |   0 |       --- |          --- |  -- |
| [0.30, 0.40) |   0 |       --- |          --- |  -- |
| [0.40, 0.50) |   0 |       --- |          --- |  -- |
| [0.50, 0.60) |   4 |     0.500 |        0.750 | -25.0pp |
| [0.60, 0.70) | 114 |     0.687 |        0.737 | -5.0pp |
| [0.70, 0.80) | 1082 |     0.742 |        0.737 | +0.6pp |
| [0.80, 0.90) | 228 |     0.832 |        0.820 | +1.2pp |
| [0.90, 1.00) |   0 |       --- |          --- |  -- |

## Fitted breakpoints

```
raw=0.550  ->  calibrated=0.500
raw=0.568  ->  calibrated=0.688
raw=0.642  ->  calibrated=0.702
raw=0.691  ->  calibrated=0.722
raw=0.739  ->  calibrated=0.724
raw=0.794  ->  calibrated=0.741
raw=0.838  ->  calibrated=0.785
raw=0.875  ->  calibrated=0.797
raw=0.916  ->  calibrated=0.818
raw=0.952  ->  calibrated=0.889
```

## Decision

- **Propose update?** `True`
- Current live ECE: `0.054`
- New candidate ECE: `0.011`
- ECE drop: `+0.043` (threshold for propose: `0.030`)
- Reason: new ECE 0.011 beats current 0.054 by +0.043
