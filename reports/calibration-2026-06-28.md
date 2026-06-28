# Calibration report -- 2026-06-28

## Summary

- Fitted on **n=1462** pairs.
- ECE: **0.054 -> 0.015** (+3.9pp on the training set)
- Brier: **0.190 -> 0.186** (+0.004)
- Source: `/home/runner/work/sre-agent/sre-agent/.feedback-ci`

## Reliability diagram (before)

| bin           |   N | mean_pred | frac_correct | gap |
|---------------|-----|-----------|--------------|-----|
| [0.00, 0.10) |   0 |       --- |          --- |  -- |
| [0.10, 0.20) |   0 |       --- |          --- |  -- |
| [0.20, 0.30) |   0 |       --- |          --- |  -- |
| [0.30, 0.40) |   0 |       --- |          --- |  -- |
| [0.40, 0.50) |   0 |       --- |          --- |  -- |
| [0.50, 0.60) |  71 |     0.581 |        0.775 | -19.3pp |
| [0.60, 0.70) | 304 |     0.669 |        0.688 | -1.8pp |
| [0.70, 0.80) | 441 |     0.752 |        0.707 | +4.4pp |
| [0.80, 0.90) | 467 |     0.842 |        0.794 | +4.8pp |
| [0.90, 1.00) | 179 |     0.924 |        0.827 | +9.7pp |

## Reliability diagram (after applying fitted calibrator)

| bin           |   N | mean_pred | frac_correct | gap |
|---------------|-----|-----------|--------------|-----|
| [0.00, 0.10) |   0 |       --- |          --- |  -- |
| [0.10, 0.20) |   0 |       --- |          --- |  -- |
| [0.20, 0.30) |   0 |       --- |          --- |  -- |
| [0.30, 0.40) |   0 |       --- |          --- |  -- |
| [0.40, 0.50) |   0 |       --- |          --- |  -- |
| [0.50, 0.60) |   6 |     0.500 |        0.833 | -33.3pp |
| [0.60, 0.70) | 142 |     0.686 |        0.754 | -6.7pp |
| [0.70, 0.80) | 864 |     0.717 |        0.716 | +0.0pp |
| [0.80, 0.90) | 431 |     0.827 |        0.812 | +1.5pp |
| [0.90, 1.00) |  19 |     0.937 |        0.737 | +20.0pp |

## Fitted breakpoints

```
raw=0.550  ->  calibrated=0.500
raw=0.560  ->  calibrated=0.667
raw=0.650  ->  calibrated=0.700
raw=0.734  ->  calibrated=0.701
raw=0.791  ->  calibrated=0.715
raw=0.814  ->  calibrated=0.759
raw=0.848  ->  calibrated=0.814
raw=0.896  ->  calibrated=0.818
raw=0.916  ->  calibrated=0.846
raw=0.934  ->  calibrated=0.862
raw=0.970  ->  calibrated=1.000
```

## Decision

- **Propose update?** `True`
- Current live ECE: `0.054`
- New candidate ECE: `0.015`
- ECE drop: `+0.039` (threshold for propose: `0.030`)
- Reason: new ECE 0.015 beats current 0.054 by +0.039
