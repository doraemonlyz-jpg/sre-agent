# Calibration report -- 2026-05-24

## Summary

- Fitted on **n=1469** pairs.
- ECE: **0.058 -> 0.022** (+3.6pp on the training set)
- Brier: **0.188 -> 0.185** (+0.003)
- Source: `/home/runner/work/sre-agent/sre-agent/.feedback-ci`

## Reliability diagram (before)

| bin           |   N | mean_pred | frac_correct | gap |
|---------------|-----|-----------|--------------|-----|
| [0.00, 0.10) |   0 |       --- |          --- |  -- |
| [0.10, 0.20) |   0 |       --- |          --- |  -- |
| [0.20, 0.30) |   0 |       --- |          --- |  -- |
| [0.30, 0.40) |   0 |       --- |          --- |  -- |
| [0.40, 0.50) |   0 |       --- |          --- |  -- |
| [0.50, 0.60) |  76 |     0.579 |        0.750 | -17.1pp |
| [0.60, 0.70) | 319 |     0.668 |        0.727 | -5.9pp |
| [0.70, 0.80) | 434 |     0.750 |        0.737 | +1.2pp |
| [0.80, 0.90) | 447 |     0.842 |        0.792 | +5.0pp |
| [0.90, 1.00) | 193 |     0.921 |        0.793 | +12.8pp |

## Reliability diagram (after applying fitted calibrator)

| bin           |   N | mean_pred | frac_correct | gap |
|---------------|-----|-----------|--------------|-----|
| [0.00, 0.10) |   0 |       --- |          --- |  -- |
| [0.10, 0.20) |   0 |       --- |          --- |  -- |
| [0.20, 0.30) |   0 |       --- |          --- |  -- |
| [0.30, 0.40) |   0 |       --- |          --- |  -- |
| [0.40, 0.50) |   0 |       --- |          --- |  -- |
| [0.50, 0.60) |  44 |     0.547 |        0.750 | -20.3pp |
| [0.60, 0.70) |  59 |     0.645 |        0.780 | -13.4pp |
| [0.70, 0.80) | 1090 |     0.750 |        0.750 | -0.1pp |
| [0.80, 0.90) | 228 |     0.822 |        0.798 | +2.4pp |
| [0.90, 1.00) |  48 |     0.963 |        0.771 | +19.2pp |

## Fitted breakpoints

```
raw=0.550  ->  calibrated=0.500
raw=0.632  ->  calibrated=0.719
raw=0.680  ->  calibrated=0.722
raw=0.741  ->  calibrated=0.736
raw=0.800  ->  calibrated=0.750
raw=0.807  ->  calibrated=0.767
raw=0.836  ->  calibrated=0.799
raw=0.875  ->  calibrated=0.800
raw=0.917  ->  calibrated=0.817
raw=0.950  ->  calibrated=1.000
```

## Decision

- **Propose update?** `True`
- Current live ECE: `0.058`
- New candidate ECE: `0.022`
- ECE drop: `+0.036` (threshold for propose: `0.030`)
- Reason: new ECE 0.022 beats current 0.058 by +0.036
