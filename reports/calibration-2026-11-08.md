# Calibration report -- 2026-11-08

## Summary

- Fitted on **n=1477** pairs.
- ECE: **0.069 -> 0.008** (+6.0pp on the training set)
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
| [0.60, 0.70) | 320 |     0.669 |        0.709 | -4.1pp |
| [0.70, 0.80) | 443 |     0.749 |        0.718 | +3.1pp |
| [0.80, 0.90) | 454 |     0.842 |        0.744 | +9.7pp |
| [0.90, 1.00) | 184 |     0.921 |        0.804 | +11.7pp |

## Reliability diagram (after applying fitted calibrator)

| bin           |   N | mean_pred | frac_correct | gap |
|---------------|-----|-----------|--------------|-----|
| [0.00, 0.10) |   4 |     0.000 |        0.500 | -50.0pp |
| [0.10, 0.20) |   0 |       --- |          --- |  -- |
| [0.20, 0.30) |   0 |       --- |          --- |  -- |
| [0.30, 0.40) |   0 |       --- |          --- |  -- |
| [0.40, 0.50) |  14 |     0.465 |        0.786 | -32.1pp |
| [0.50, 0.60) |   0 |       --- |          --- |  -- |
| [0.60, 0.70) |  58 |     0.685 |        0.690 | -0.4pp |
| [0.70, 0.80) | 1255 |     0.727 |        0.728 | -0.1pp |
| [0.80, 0.90) | 146 |     0.829 |        0.801 | +2.7pp |
| [0.90, 1.00) |   0 |       --- |          --- |  -- |

## Fitted breakpoints

```
raw=0.550  ->  calibrated=0.000
raw=0.564  ->  calibrated=0.645
raw=0.588  ->  calibrated=0.697
raw=0.668  ->  calibrated=0.710
raw=0.733  ->  calibrated=0.714
raw=0.787  ->  calibrated=0.717
raw=0.818  ->  calibrated=0.731
raw=0.839  ->  calibrated=0.741
raw=0.860  ->  calibrated=0.750
raw=0.873  ->  calibrated=0.765
raw=0.890  ->  calibrated=0.786
raw=0.906  ->  calibrated=0.807
raw=0.933  ->  calibrated=0.838
raw=0.952  ->  calibrated=0.846
```

## Decision

- **Propose update?** `True`
- Current live ECE: `0.069`
- New candidate ECE: `0.008`
- ECE drop: `+0.060` (threshold for propose: `0.030`)
- Reason: new ECE 0.008 beats current 0.069 by +0.060
