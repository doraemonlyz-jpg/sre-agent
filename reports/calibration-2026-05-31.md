# Calibration report -- 2026-05-31

## Summary

- Fitted on **n=1474** pairs.
- ECE: **0.073 -> 0.009** (+6.4pp on the training set)
- Brier: **0.203 -> 0.196** (+0.007)
- Source: `/home/runner/work/sre-agent/sre-agent/.feedback-ci`

## Reliability diagram (before)

| bin           |   N | mean_pred | frac_correct | gap |
|---------------|-----|-----------|--------------|-----|
| [0.00, 0.10) |   0 |       --- |          --- |  -- |
| [0.10, 0.20) |   0 |       --- |          --- |  -- |
| [0.20, 0.30) |   0 |       --- |          --- |  -- |
| [0.30, 0.40) |   0 |       --- |          --- |  -- |
| [0.40, 0.50) |   0 |       --- |          --- |  -- |
| [0.50, 0.60) |  73 |     0.580 |        0.685 | -10.5pp |
| [0.60, 0.70) | 322 |     0.669 |        0.714 | -4.6pp |
| [0.70, 0.80) | 438 |     0.750 |        0.715 | +3.5pp |
| [0.80, 0.90) | 456 |     0.842 |        0.743 | +9.9pp |
| [0.90, 1.00) | 185 |     0.922 |        0.789 | +13.3pp |

## Reliability diagram (after applying fitted calibrator)

| bin           |   N | mean_pred | frac_correct | gap |
|---------------|-----|-----------|--------------|-----|
| [0.00, 0.10) |   0 |       --- |          --- |  -- |
| [0.10, 0.20) |   0 |       --- |          --- |  -- |
| [0.20, 0.30) |   0 |       --- |          --- |  -- |
| [0.30, 0.40) |   0 |       --- |          --- |  -- |
| [0.40, 0.50) |   0 |       --- |          --- |  -- |
| [0.50, 0.60) |  16 |     0.500 |        0.688 | -18.8pp |
| [0.60, 0.70) | 107 |     0.686 |        0.710 | -2.4pp |
| [0.70, 0.80) | 1202 |     0.730 |        0.728 | +0.2pp |
| [0.80, 0.90) | 149 |     0.814 |        0.779 | +3.5pp |
| [0.90, 1.00) |   0 |       --- |          --- |  -- |

## Fitted breakpoints

```
raw=0.550  ->  calibrated=0.500
raw=0.560  ->  calibrated=0.500
raw=0.566  ->  calibrated=0.611
raw=0.577  ->  calibrated=0.667
raw=0.587  ->  calibrated=0.692
raw=0.720  ->  calibrated=0.710
raw=0.838  ->  calibrated=0.746
raw=0.877  ->  calibrated=0.757
raw=0.906  ->  calibrated=0.810
raw=0.939  ->  calibrated=0.817
```

## Decision

- **Propose update?** `True`
- Current live ECE: `0.073`
- New candidate ECE: `0.009`
- ECE drop: `+0.064` (threshold for propose: `0.030`)
- Reason: new ECE 0.009 beats current 0.073 by +0.064
