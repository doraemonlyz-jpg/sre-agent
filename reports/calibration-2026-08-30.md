# Calibration report -- 2026-08-30

## Summary

- Fitted on **n=1443** pairs.
- ECE: **0.054 -> 0.005** (+4.9pp on the training set)
- Brier: **0.190 -> 0.185** (+0.005)
- Source: `/home/runner/work/sre-agent/sre-agent/.feedback-ci`

## Reliability diagram (before)

| bin           |   N | mean_pred | frac_correct | gap |
|---------------|-----|-----------|--------------|-----|
| [0.00, 0.10) |   0 |       --- |          --- |  -- |
| [0.10, 0.20) |   0 |       --- |          --- |  -- |
| [0.20, 0.30) |   0 |       --- |          --- |  -- |
| [0.30, 0.40) |   0 |       --- |          --- |  -- |
| [0.40, 0.50) |   0 |       --- |          --- |  -- |
| [0.50, 0.60) |  69 |     0.581 |        0.725 | -14.4pp |
| [0.60, 0.70) | 338 |     0.669 |        0.713 | -4.4pp |
| [0.70, 0.80) | 416 |     0.750 |        0.736 | +1.5pp |
| [0.80, 0.90) | 434 |     0.841 |        0.788 | +5.3pp |
| [0.90, 1.00) | 186 |     0.923 |        0.796 | +12.7pp |

## Reliability diagram (after applying fitted calibrator)

| bin           |   N | mean_pred | frac_correct | gap |
|---------------|-----|-----------|--------------|-----|
| [0.00, 0.10) |   0 |       --- |          --- |  -- |
| [0.10, 0.20) |   0 |       --- |          --- |  -- |
| [0.20, 0.30) |   0 |       --- |          --- |  -- |
| [0.30, 0.40) |   0 |       --- |          --- |  -- |
| [0.40, 0.50) |   0 |       --- |          --- |  -- |
| [0.50, 0.60) |   0 |       --- |          --- |  -- |
| [0.60, 0.70) |  69 |     0.690 |        0.725 | -3.4pp |
| [0.70, 0.80) | 1077 |     0.743 |        0.742 | +0.1pp |
| [0.80, 0.90) | 297 |     0.813 |        0.801 | +1.1pp |
| [0.90, 1.00) |   0 |       --- |          --- |  -- |

## Fitted breakpoints

```
raw=0.553  ->  calibrated=0.667
raw=0.577  ->  calibrated=0.696
raw=0.646  ->  calibrated=0.705
raw=0.671  ->  calibrated=0.714
raw=0.723  ->  calibrated=0.718
raw=0.792  ->  calibrated=0.763
raw=0.851  ->  calibrated=0.796
raw=0.919  ->  calibrated=0.818
raw=0.947  ->  calibrated=0.821
```

## Decision

- **Propose update?** `True`
- Current live ECE: `0.054`
- New candidate ECE: `0.005`
- ECE drop: `+0.049` (threshold for propose: `0.030`)
- Reason: new ECE 0.005 beats current 0.054 by +0.049
