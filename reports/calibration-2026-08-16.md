# Calibration report -- 2026-08-16

## Summary

- Fitted on **n=1466** pairs.
- ECE: **0.084 -> 0.023** (+6.1pp on the training set)
- Brier: **0.199 -> 0.192** (+0.006)
- Source: `/home/runner/work/sre-agent/sre-agent/.feedback-ci`

## Reliability diagram (before)

| bin           |   N | mean_pred | frac_correct | gap |
|---------------|-----|-----------|--------------|-----|
| [0.00, 0.10) |   0 |       --- |          --- |  -- |
| [0.10, 0.20) |   0 |       --- |          --- |  -- |
| [0.20, 0.30) |   0 |       --- |          --- |  -- |
| [0.30, 0.40) |   0 |       --- |          --- |  -- |
| [0.40, 0.50) |   0 |       --- |          --- |  -- |
| [0.50, 0.60) |  67 |     0.580 |        0.716 | -13.6pp |
| [0.60, 0.70) | 326 |     0.669 |        0.748 | -7.9pp |
| [0.70, 0.80) | 418 |     0.750 |        0.677 | +7.3pp |
| [0.80, 0.90) | 454 |     0.843 |        0.793 | +5.0pp |
| [0.90, 1.00) | 201 |     0.924 |        0.746 | +17.8pp |

## Reliability diagram (after applying fitted calibrator)

| bin           |   N | mean_pred | frac_correct | gap |
|---------------|-----|-----------|--------------|-----|
| [0.00, 0.10) |   4 |     0.000 |        0.250 | -25.0pp |
| [0.10, 0.20) |   0 |       --- |          --- |  -- |
| [0.20, 0.30) |   0 |       --- |          --- |  -- |
| [0.30, 0.40) |   0 |       --- |          --- |  -- |
| [0.40, 0.50) |   0 |       --- |          --- |  -- |
| [0.50, 0.60) |  11 |     0.556 |        0.545 | +1.0pp |
| [0.60, 0.70) | 235 |     0.665 |        0.757 | -9.3pp |
| [0.70, 0.80) | 1190 |     0.747 |        0.739 | +0.8pp |
| [0.80, 0.90) |  26 |     0.826 |        0.769 | +5.6pp |
| [0.90, 1.00) |   0 |       --- |          --- |  -- |

## Fitted breakpoints

```
raw=0.550  ->  calibrated=0.000
raw=0.558  ->  calibrated=0.500
raw=0.562  ->  calibrated=0.600
raw=0.686  ->  calibrated=0.706
raw=0.778  ->  calibrated=0.725
raw=0.859  ->  calibrated=0.781
raw=0.941  ->  calibrated=0.800
raw=0.953  ->  calibrated=0.833
```

## Decision

- **Propose update?** `True`
- Current live ECE: `0.084`
- New candidate ECE: `0.023`
- ECE drop: `+0.061` (threshold for propose: `0.030`)
- Reason: new ECE 0.023 beats current 0.084 by +0.061
