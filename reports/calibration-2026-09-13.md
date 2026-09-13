# Calibration report -- 2026-09-13

## Summary

- Fitted on **n=1442** pairs.
- ECE: **0.073 -> 0.036** (+3.6pp on the training set)
- Brier: **0.207 -> 0.203** (+0.004)
- Source: `/home/runner/work/sre-agent/sre-agent/.feedback-ci`

## Reliability diagram (before)

| bin           |   N | mean_pred | frac_correct | gap |
|---------------|-----|-----------|--------------|-----|
| [0.00, 0.10) |   0 |       --- |          --- |  -- |
| [0.10, 0.20) |   0 |       --- |          --- |  -- |
| [0.20, 0.30) |   0 |       --- |          --- |  -- |
| [0.30, 0.40) |   0 |       --- |          --- |  -- |
| [0.40, 0.50) |   0 |       --- |          --- |  -- |
| [0.50, 0.60) |  70 |     0.581 |        0.643 | -6.2pp |
| [0.60, 0.70) | 319 |     0.669 |        0.712 | -4.3pp |
| [0.70, 0.80) | 435 |     0.750 |        0.706 | +4.4pp |
| [0.80, 0.90) | 442 |     0.842 |        0.758 | +8.4pp |
| [0.90, 1.00) | 176 |     0.922 |        0.750 | +17.2pp |

## Reliability diagram (after applying fitted calibrator)

| bin           |   N | mean_pred | frac_correct | gap |
|---------------|-----|-----------|--------------|-----|
| [0.00, 0.10) |   0 |       --- |          --- |  -- |
| [0.10, 0.20) |   0 |       --- |          --- |  -- |
| [0.20, 0.30) |   0 |       --- |          --- |  -- |
| [0.30, 0.40) |   0 |       --- |          --- |  -- |
| [0.40, 0.50) |   0 |       --- |          --- |  -- |
| [0.50, 0.60) |   0 |       --- |          --- |  -- |
| [0.60, 0.70) | 432 |     0.672 |        0.706 | -3.4pp |
| [0.70, 0.80) | 792 |     0.736 |        0.726 | +1.0pp |
| [0.80, 0.90) | 113 |     0.846 |        0.770 | +7.6pp |
| [0.90, 1.00) | 105 |     0.950 |        0.752 | +19.8pp |

## Fitted breakpoints

```
raw=0.581  ->  calibrated=0.634
raw=0.725  ->  calibrated=0.703
raw=0.875  ->  calibrated=0.772
raw=0.950  ->  calibrated=1.000
```

## Decision

- **Propose update?** `True`
- Current live ECE: `0.073`
- New candidate ECE: `0.036`
- ECE drop: `+0.036` (threshold for propose: `0.030`)
- Reason: new ECE 0.036 beats current 0.073 by +0.036
