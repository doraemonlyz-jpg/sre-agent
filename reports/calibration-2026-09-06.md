# Calibration report -- 2026-09-06

## Summary

- Fitted on **n=1463** pairs.
- ECE: **0.065 -> 0.017** (+4.9pp on the training set)
- Brier: **0.198 -> 0.192** (+0.005)
- Source: `/home/runner/work/sre-agent/sre-agent/.feedback-ci`

## Reliability diagram (before)

| bin           |   N | mean_pred | frac_correct | gap |
|---------------|-----|-----------|--------------|-----|
| [0.00, 0.10) |   0 |       --- |          --- |  -- |
| [0.10, 0.20) |   0 |       --- |          --- |  -- |
| [0.20, 0.30) |   0 |       --- |          --- |  -- |
| [0.30, 0.40) |   0 |       --- |          --- |  -- |
| [0.40, 0.50) |   0 |       --- |          --- |  -- |
| [0.50, 0.60) |  79 |     0.581 |        0.747 | -16.6pp |
| [0.60, 0.70) | 301 |     0.669 |        0.698 | -2.9pp |
| [0.70, 0.80) | 444 |     0.751 |        0.718 | +3.2pp |
| [0.80, 0.90) | 447 |     0.840 |        0.758 | +8.1pp |
| [0.90, 1.00) | 192 |     0.923 |        0.802 | +12.1pp |

## Reliability diagram (after applying fitted calibrator)

| bin           |   N | mean_pred | frac_correct | gap |
|---------------|-----|-----------|--------------|-----|
| [0.00, 0.10) |   0 |       --- |          --- |  -- |
| [0.10, 0.20) |   0 |       --- |          --- |  -- |
| [0.20, 0.30) |   0 |       --- |          --- |  -- |
| [0.30, 0.40) |   0 |       --- |          --- |  -- |
| [0.40, 0.50) |   0 |       --- |          --- |  -- |
| [0.50, 0.60) |  17 |     0.600 |        0.706 | -10.6pp |
| [0.60, 0.70) | 143 |     0.662 |        0.741 | -7.9pp |
| [0.70, 0.80) | 1143 |     0.735 |        0.729 | +0.7pp |
| [0.80, 0.90) | 155 |     0.830 |        0.806 | +2.4pp |
| [0.90, 1.00) |   5 |     1.000 |        1.000 | +0.0pp |

## Fitted breakpoints

```
raw=0.564  ->  calibrated=0.600
raw=0.641  ->  calibrated=0.697
raw=0.711  ->  calibrated=0.709
raw=0.740  ->  calibrated=0.714
raw=0.750  ->  calibrated=0.739
raw=0.783  ->  calibrated=0.742
raw=0.800  ->  calibrated=0.750
raw=0.814  ->  calibrated=0.750
raw=0.848  ->  calibrated=0.752
raw=0.894  ->  calibrated=0.773
raw=0.924  ->  calibrated=0.830
raw=0.944  ->  calibrated=0.838
raw=0.960  ->  calibrated=1.000
raw=0.970  ->  calibrated=1.000
raw=0.980  ->  calibrated=1.000
```

## Decision

- **Propose update?** `True`
- Current live ECE: `0.065`
- New candidate ECE: `0.017`
- ECE drop: `+0.049` (threshold for propose: `0.030`)
- Reason: new ECE 0.017 beats current 0.065 by +0.049
