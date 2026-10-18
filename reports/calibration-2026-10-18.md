# Calibration report -- 2026-10-18

## Summary

- Fitted on **n=1428** pairs.
- ECE: **0.060 -> 0.018** (+4.2pp on the training set)
- Brier: **0.197 -> 0.193** (+0.005)
- Source: `/home/runner/work/sre-agent/sre-agent/.feedback-ci`

## Reliability diagram (before)

| bin           |   N | mean_pred | frac_correct | gap |
|---------------|-----|-----------|--------------|-----|
| [0.00, 0.10) |   0 |       --- |          --- |  -- |
| [0.10, 0.20) |   0 |       --- |          --- |  -- |
| [0.20, 0.30) |   0 |       --- |          --- |  -- |
| [0.30, 0.40) |   0 |       --- |          --- |  -- |
| [0.40, 0.50) |   0 |       --- |          --- |  -- |
| [0.50, 0.60) |  75 |     0.581 |        0.747 | -16.5pp |
| [0.60, 0.70) | 317 |     0.670 |        0.694 | -2.4pp |
| [0.70, 0.80) | 433 |     0.751 |        0.711 | +3.9pp |
| [0.80, 0.90) | 430 |     0.839 |        0.770 | +6.9pp |
| [0.90, 1.00) | 173 |     0.923 |        0.809 | +11.3pp |

## Reliability diagram (after applying fitted calibrator)

| bin           |   N | mean_pred | frac_correct | gap |
|---------------|-----|-----------|--------------|-----|
| [0.00, 0.10) |   0 |       --- |          --- |  -- |
| [0.10, 0.20) |   0 |       --- |          --- |  -- |
| [0.20, 0.30) |   0 |       --- |          --- |  -- |
| [0.30, 0.40) |   0 |       --- |          --- |  -- |
| [0.40, 0.50) |   0 |       --- |          --- |  -- |
| [0.50, 0.60) |   0 |       --- |          --- |  -- |
| [0.60, 0.70) | 345 |     0.673 |        0.707 | -3.5pp |
| [0.70, 0.80) | 878 |     0.747 |        0.736 | +1.1pp |
| [0.80, 0.90) | 203 |     0.823 |        0.803 | +2.0pp |
| [0.90, 1.00) |   2 |     1.000 |        1.000 | +0.0pp |

## Fitted breakpoints

```
raw=0.556  ->  calibrated=0.625
raw=0.566  ->  calibrated=0.625
raw=0.685  ->  calibrated=0.695
raw=0.760  ->  calibrated=0.739
raw=0.791  ->  calibrated=0.742
raw=0.847  ->  calibrated=0.777
raw=0.906  ->  calibrated=0.814
raw=0.932  ->  calibrated=0.821
raw=0.980  ->  calibrated=1.000
```

## Decision

- **Propose update?** `True`
- Current live ECE: `0.060`
- New candidate ECE: `0.018`
- ECE drop: `+0.042` (threshold for propose: `0.030`)
- Reason: new ECE 0.018 beats current 0.060 by +0.042
