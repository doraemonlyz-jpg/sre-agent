# Calibration report -- 2026-08-02

## Summary

- Fitted on **n=1482** pairs.
- ECE: **0.050 -> 0.013** (+3.7pp on the training set)
- Brier: **0.191 -> 0.186** (+0.005)
- Source: `/home/runner/work/sre-agent/sre-agent/.feedback-ci`

## Reliability diagram (before)

| bin           |   N | mean_pred | frac_correct | gap |
|---------------|-----|-----------|--------------|-----|
| [0.00, 0.10) |   0 |       --- |          --- |  -- |
| [0.10, 0.20) |   0 |       --- |          --- |  -- |
| [0.20, 0.30) |   0 |       --- |          --- |  -- |
| [0.30, 0.40) |   0 |       --- |          --- |  -- |
| [0.40, 0.50) |   0 |       --- |          --- |  -- |
| [0.50, 0.60) |  68 |     0.579 |        0.721 | -14.1pp |
| [0.60, 0.70) | 347 |     0.669 |        0.703 | -3.4pp |
| [0.70, 0.80) | 444 |     0.749 |        0.730 | +1.9pp |
| [0.80, 0.90) | 445 |     0.840 |        0.789 | +5.1pp |
| [0.90, 1.00) | 178 |     0.924 |        0.803 | +12.0pp |

## Reliability diagram (after applying fitted calibrator)

| bin           |   N | mean_pred | frac_correct | gap |
|---------------|-----|-----------|--------------|-----|
| [0.00, 0.10) |   0 |       --- |          --- |  -- |
| [0.10, 0.20) |   0 |       --- |          --- |  -- |
| [0.20, 0.30) |   0 |       --- |          --- |  -- |
| [0.30, 0.40) |   6 |     0.333 |        0.333 | +0.0pp |
| [0.40, 0.50) |   0 |       --- |          --- |  -- |
| [0.50, 0.60) |   0 |       --- |          --- |  -- |
| [0.60, 0.70) | 115 |     0.685 |        0.783 | -9.8pp |
| [0.70, 0.80) | 1037 |     0.733 |        0.726 | +0.7pp |
| [0.80, 0.90) | 324 |     0.824 |        0.821 | +0.3pp |
| [0.90, 1.00) |   0 |       --- |          --- |  -- |

## Fitted breakpoints

```
raw=0.550  ->  calibrated=0.333
raw=0.560  ->  calibrated=0.667
raw=0.646  ->  calibrated=0.702
raw=0.752  ->  calibrated=0.721
raw=0.821  ->  calibrated=0.765
raw=0.884  ->  calibrated=0.830
```

## Decision

- **Propose update?** `True`
- Current live ECE: `0.050`
- New candidate ECE: `0.013`
- ECE drop: `+0.037` (threshold for propose: `0.030`)
- Reason: new ECE 0.013 beats current 0.050 by +0.037
