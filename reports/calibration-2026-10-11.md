# Calibration report -- 2026-10-11

## Summary

- Fitted on **n=1465** pairs.
- ECE: **0.076 -> 0.012** (+6.3pp on the training set)
- Brier: **0.195 -> 0.189** (+0.006)
- Source: `/home/runner/work/sre-agent/sre-agent/.feedback-ci`

## Reliability diagram (before)

| bin           |   N | mean_pred | frac_correct | gap |
|---------------|-----|-----------|--------------|-----|
| [0.00, 0.10) |   0 |       --- |          --- |  -- |
| [0.10, 0.20) |   0 |       --- |          --- |  -- |
| [0.20, 0.30) |   0 |       --- |          --- |  -- |
| [0.30, 0.40) |   0 |       --- |          --- |  -- |
| [0.40, 0.50) |   0 |       --- |          --- |  -- |
| [0.50, 0.60) |  76 |     0.581 |        0.750 | -16.9pp |
| [0.60, 0.70) | 303 |     0.668 |        0.746 | -7.8pp |
| [0.70, 0.80) | 446 |     0.749 |        0.713 | +3.6pp |
| [0.80, 0.90) | 447 |     0.842 |        0.781 | +6.1pp |
| [0.90, 1.00) | 193 |     0.920 |        0.762 | +15.8pp |

## Reliability diagram (after applying fitted calibrator)

| bin           |   N | mean_pred | frac_correct | gap |
|---------------|-----|-----------|--------------|-----|
| [0.00, 0.10) |   4 |     0.000 |        0.500 | -50.0pp |
| [0.10, 0.20) |   0 |       --- |          --- |  -- |
| [0.20, 0.30) |   0 |       --- |          --- |  -- |
| [0.30, 0.40) |   0 |       --- |          --- |  -- |
| [0.40, 0.50) |   0 |       --- |          --- |  -- |
| [0.50, 0.60) |  11 |     0.517 |        0.818 | -30.1pp |
| [0.60, 0.70) |  85 |     0.691 |        0.788 | -9.7pp |
| [0.70, 0.80) | 1365 |     0.750 |        0.747 | +0.3pp |
| [0.80, 0.90) |   0 |       --- |          --- |  -- |
| [0.90, 1.00) |   0 |       --- |          --- |  -- |

## Fitted breakpoints

```
raw=0.550  ->  calibrated=0.000
raw=0.563  ->  calibrated=0.682
raw=0.715  ->  calibrated=0.727
raw=0.810  ->  calibrated=0.741
raw=0.838  ->  calibrated=0.779
raw=0.906  ->  calibrated=0.797
```

## Decision

- **Propose update?** `True`
- Current live ECE: `0.076`
- New candidate ECE: `0.012`
- ECE drop: `+0.063` (threshold for propose: `0.030`)
- Reason: new ECE 0.012 beats current 0.076 by +0.063
