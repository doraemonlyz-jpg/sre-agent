# Calibration report -- 2026-08-09

## Summary

- Fitted on **n=1471** pairs.
- ECE: **0.083 -> 0.009** (+7.4pp on the training set)
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
| [0.50, 0.60) |  66 |     0.577 |        0.697 | -12.0pp |
| [0.60, 0.70) | 312 |     0.669 |        0.737 | -6.9pp |
| [0.70, 0.80) | 436 |     0.748 |        0.702 | +4.6pp |
| [0.80, 0.90) | 442 |     0.841 |        0.774 | +6.7pp |
| [0.90, 1.00) | 215 |     0.924 |        0.721 | +20.3pp |

## Reliability diagram (after applying fitted calibrator)

| bin           |   N | mean_pred | frac_correct | gap |
|---------------|-----|-----------|--------------|-----|
| [0.00, 0.10) |   0 |       --- |          --- |  -- |
| [0.10, 0.20) |   0 |       --- |          --- |  -- |
| [0.20, 0.30) |   0 |       --- |          --- |  -- |
| [0.30, 0.40) |   0 |       --- |          --- |  -- |
| [0.40, 0.50) |   0 |       --- |          --- |  -- |
| [0.50, 0.60) |   8 |     0.500 |        0.625 | -12.5pp |
| [0.60, 0.70) | 109 |     0.687 |        0.752 | -6.6pp |
| [0.70, 0.80) | 1354 |     0.737 |        0.733 | +0.4pp |
| [0.80, 0.90) |   0 |       --- |          --- |  -- |
| [0.90, 1.00) |   0 |       --- |          --- |  -- |

## Fitted breakpoints

```
raw=0.550  ->  calibrated=0.500
raw=0.552  ->  calibrated=0.625
raw=0.560  ->  calibrated=0.667
raw=0.574  ->  calibrated=0.680
raw=0.686  ->  calibrated=0.710
raw=0.769  ->  calibrated=0.728
raw=0.857  ->  calibrated=0.758
raw=0.941  ->  calibrated=0.773
```

## Decision

- **Propose update?** `True`
- Current live ECE: `0.083`
- New candidate ECE: `0.009`
- ECE drop: `+0.074` (threshold for propose: `0.030`)
- Reason: new ECE 0.009 beats current 0.083 by +0.074
