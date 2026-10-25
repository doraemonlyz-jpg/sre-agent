# Calibration report -- 2026-10-25

## Summary

- Fitted on **n=1463** pairs.
- ECE: **0.056 -> 0.009** (+4.7pp on the training set)
- Brier: **0.197 -> 0.191** (+0.006)
- Source: `/home/runner/work/sre-agent/sre-agent/.feedback-ci`

## Reliability diagram (before)

| bin           |   N | mean_pred | frac_correct | gap |
|---------------|-----|-----------|--------------|-----|
| [0.00, 0.10) |   0 |       --- |          --- |  -- |
| [0.10, 0.20) |   0 |       --- |          --- |  -- |
| [0.20, 0.30) |   0 |       --- |          --- |  -- |
| [0.30, 0.40) |   0 |       --- |          --- |  -- |
| [0.40, 0.50) |   0 |       --- |          --- |  -- |
| [0.50, 0.60) |  75 |     0.581 |        0.653 | -7.3pp |
| [0.60, 0.70) | 329 |     0.669 |        0.708 | -3.9pp |
| [0.70, 0.80) | 439 |     0.749 |        0.713 | +3.6pp |
| [0.80, 0.90) | 446 |     0.840 |        0.789 | +5.1pp |
| [0.90, 1.00) | 174 |     0.922 |        0.782 | +14.1pp |

## Reliability diagram (after applying fitted calibrator)

| bin           |   N | mean_pred | frac_correct | gap |
|---------------|-----|-----------|--------------|-----|
| [0.00, 0.10) |   0 |       --- |          --- |  -- |
| [0.10, 0.20) |   0 |       --- |          --- |  -- |
| [0.20, 0.30) |   0 |       --- |          --- |  -- |
| [0.30, 0.40) |   0 |       --- |          --- |  -- |
| [0.40, 0.50) |   0 |       --- |          --- |  -- |
| [0.50, 0.60) |  29 |     0.555 |        0.552 | +0.3pp |
| [0.60, 0.70) |  46 |     0.658 |        0.717 | -6.0pp |
| [0.70, 0.80) | 1388 |     0.752 |        0.745 | +0.7pp |
| [0.80, 0.90) |   0 |       --- |          --- |  -- |
| [0.90, 1.00) |   0 |       --- |          --- |  -- |

## Fitted breakpoints

```
raw=0.565  ->  calibrated=0.545
raw=0.585  ->  calibrated=0.625
raw=0.603  ->  calibrated=0.711
raw=0.717  ->  calibrated=0.712
raw=0.831  ->  calibrated=0.786
raw=0.912  ->  calibrated=0.796
```

## Decision

- **Propose update?** `True`
- Current live ECE: `0.056`
- New candidate ECE: `0.009`
- ECE drop: `+0.047` (threshold for propose: `0.030`)
- Reason: new ECE 0.009 beats current 0.056 by +0.047
