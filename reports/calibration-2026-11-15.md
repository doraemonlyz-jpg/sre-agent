# Calibration report -- 2026-11-15

## Summary

- Fitted on **n=1467** pairs.
- ECE: **0.083 -> 0.019** (+6.4pp on the training set)
- Brier: **0.205 -> 0.196** (+0.009)
- Source: `/home/runner/work/sre-agent/sre-agent/.feedback-ci`

## Reliability diagram (before)

| bin           |   N | mean_pred | frac_correct | gap |
|---------------|-----|-----------|--------------|-----|
| [0.00, 0.10) |   0 |       --- |          --- |  -- |
| [0.10, 0.20) |   0 |       --- |          --- |  -- |
| [0.20, 0.30) |   0 |       --- |          --- |  -- |
| [0.30, 0.40) |   0 |       --- |          --- |  -- |
| [0.40, 0.50) |   0 |       --- |          --- |  -- |
| [0.50, 0.60) |  82 |     0.576 |        0.744 | -16.8pp |
| [0.60, 0.70) | 329 |     0.668 |        0.726 | -5.9pp |
| [0.70, 0.80) | 439 |     0.748 |        0.699 | +4.8pp |
| [0.80, 0.90) | 435 |     0.841 |        0.743 | +9.8pp |
| [0.90, 1.00) | 182 |     0.921 |        0.786 | +13.6pp |

## Reliability diagram (after applying fitted calibrator)

| bin           |   N | mean_pred | frac_correct | gap |
|---------------|-----|-----------|--------------|-----|
| [0.00, 0.10) |   0 |       --- |          --- |  -- |
| [0.10, 0.20) |   0 |       --- |          --- |  -- |
| [0.20, 0.30) |   0 |       --- |          --- |  -- |
| [0.30, 0.40) |   0 |       --- |          --- |  -- |
| [0.40, 0.50) |   0 |       --- |          --- |  -- |
| [0.50, 0.60) |   0 |       --- |          --- |  -- |
| [0.60, 0.70) | 214 |     0.686 |        0.762 | -7.6pp |
| [0.70, 0.80) | 1109 |     0.727 |        0.720 | +0.7pp |
| [0.80, 0.90) | 144 |     0.803 |        0.778 | +2.5pp |
| [0.90, 1.00) |   0 |       --- |          --- |  -- |

## Fitted breakpoints

```
raw=0.553  ->  calibrated=0.667
raw=0.706  ->  calibrated=0.712
raw=0.826  ->  calibrated=0.725
raw=0.860  ->  calibrated=0.744
raw=0.872  ->  calibrated=0.769
raw=0.880  ->  calibrated=0.778
raw=0.914  ->  calibrated=0.803
```

## Decision

- **Propose update?** `True`
- Current live ECE: `0.083`
- New candidate ECE: `0.019`
- ECE drop: `+0.064` (threshold for propose: `0.030`)
- Reason: new ECE 0.019 beats current 0.083 by +0.064
