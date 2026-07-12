# Calibration report -- 2026-07-12

## Summary

- Fitted on **n=1486** pairs.
- ECE: **0.055 -> 0.013** (+4.3pp on the training set)
- Brier: **0.189 -> 0.184** (+0.005)
- Source: `/home/runner/work/sre-agent/sre-agent/.feedback-ci`

## Reliability diagram (before)

| bin           |   N | mean_pred | frac_correct | gap |
|---------------|-----|-----------|--------------|-----|
| [0.00, 0.10) |   0 |       --- |          --- |  -- |
| [0.10, 0.20) |   0 |       --- |          --- |  -- |
| [0.20, 0.30) |   0 |       --- |          --- |  -- |
| [0.30, 0.40) |   0 |       --- |          --- |  -- |
| [0.40, 0.50) |   0 |       --- |          --- |  -- |
| [0.50, 0.60) |  64 |     0.580 |        0.734 | -15.4pp |
| [0.60, 0.70) | 347 |     0.669 |        0.720 | -5.1pp |
| [0.70, 0.80) | 441 |     0.749 |        0.723 | +2.5pp |
| [0.80, 0.90) | 455 |     0.840 |        0.791 | +4.9pp |
| [0.90, 1.00) | 179 |     0.924 |        0.804 | +11.9pp |

## Reliability diagram (after applying fitted calibrator)

| bin           |   N | mean_pred | frac_correct | gap |
|---------------|-----|-----------|--------------|-----|
| [0.00, 0.10) |   0 |       --- |          --- |  -- |
| [0.10, 0.20) |   0 |       --- |          --- |  -- |
| [0.20, 0.30) |   0 |       --- |          --- |  -- |
| [0.30, 0.40) |   0 |       --- |          --- |  -- |
| [0.40, 0.50) |   0 |       --- |          --- |  -- |
| [0.50, 0.60) |   4 |     0.500 |        0.500 | +0.0pp |
| [0.60, 0.70) |  67 |     0.682 |        0.761 | -7.9pp |
| [0.70, 0.80) | 956 |     0.732 |        0.719 | +1.4pp |
| [0.80, 0.90) | 459 |     0.829 |        0.828 | +0.1pp |
| [0.90, 1.00) |   0 |       --- |          --- |  -- |

## Fitted breakpoints

```
raw=0.550  ->  calibrated=0.500
raw=0.557  ->  calibrated=0.667
raw=0.645  ->  calibrated=0.714
raw=0.750  ->  calibrated=0.717
raw=0.818  ->  calibrated=0.784
raw=0.820  ->  calibrated=0.800
raw=0.827  ->  calibrated=0.829
raw=0.887  ->  calibrated=0.829
```

## Decision

- **Propose update?** `True`
- Current live ECE: `0.055`
- New candidate ECE: `0.013`
- ECE drop: `+0.043` (threshold for propose: `0.030`)
- Reason: new ECE 0.013 beats current 0.055 by +0.043
