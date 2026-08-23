# Calibration report -- 2026-08-23

## Summary

- Fitted on **n=1458** pairs.
- ECE: **0.086 -> 0.019** (+6.6pp on the training set)
- Brier: **0.202 -> 0.195** (+0.007)
- Source: `/home/runner/work/sre-agent/sre-agent/.feedback-ci`

## Reliability diagram (before)

| bin           |   N | mean_pred | frac_correct | gap |
|---------------|-----|-----------|--------------|-----|
| [0.00, 0.10) |   0 |       --- |          --- |  -- |
| [0.10, 0.20) |   0 |       --- |          --- |  -- |
| [0.20, 0.30) |   0 |       --- |          --- |  -- |
| [0.30, 0.40) |   0 |       --- |          --- |  -- |
| [0.40, 0.50) |   0 |       --- |          --- |  -- |
| [0.50, 0.60) |  66 |     0.580 |        0.727 | -14.8pp |
| [0.60, 0.70) | 313 |     0.669 |        0.735 | -6.6pp |
| [0.70, 0.80) | 422 |     0.749 |        0.673 | +7.6pp |
| [0.80, 0.90) | 453 |     0.843 |        0.790 | +5.2pp |
| [0.90, 1.00) | 204 |     0.924 |        0.735 | +18.9pp |

## Reliability diagram (after applying fitted calibrator)

| bin           |   N | mean_pred | frac_correct | gap |
|---------------|-----|-----------|--------------|-----|
| [0.00, 0.10) |   4 |     0.000 |        0.500 | -50.0pp |
| [0.10, 0.20) |   0 |       --- |          --- |  -- |
| [0.20, 0.30) |   0 |       --- |          --- |  -- |
| [0.30, 0.40) |   0 |       --- |          --- |  -- |
| [0.40, 0.50) |   0 |       --- |          --- |  -- |
| [0.50, 0.60) |   0 |       --- |          --- |  -- |
| [0.60, 0.70) | 650 |     0.691 |        0.695 | -0.5pp |
| [0.70, 0.80) | 641 |     0.761 |        0.775 | -1.4pp |
| [0.80, 0.90) | 163 |     0.815 |        0.730 | +8.5pp |
| [0.90, 1.00) |   0 |       --- |          --- |  -- |

## Fitted breakpoints

```
raw=0.550  ->  calibrated=0.000
raw=0.552  ->  calibrated=0.500
raw=0.560  ->  calibrated=0.667
raw=0.683  ->  calibrated=0.694
raw=0.762  ->  calibrated=0.696
raw=0.790  ->  calibrated=0.753
raw=0.869  ->  calibrated=0.774
raw=0.946  ->  calibrated=0.827
```

## Decision

- **Propose update?** `True`
- Current live ECE: `0.086`
- New candidate ECE: `0.019`
- ECE drop: `+0.066` (threshold for propose: `0.030`)
- Reason: new ECE 0.019 beats current 0.086 by +0.066
