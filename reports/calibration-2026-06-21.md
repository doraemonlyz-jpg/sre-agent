# Calibration report -- 2026-06-21

## Summary

- Fitted on **n=1458** pairs.
- ECE: **0.061 -> 0.009** (+5.2pp on the training set)
- Brier: **0.197 -> 0.194** (+0.004)
- Source: `/home/runner/work/sre-agent/sre-agent/.feedback-ci`

## Reliability diagram (before)

| bin           |   N | mean_pred | frac_correct | gap |
|---------------|-----|-----------|--------------|-----|
| [0.00, 0.10) |   0 |       --- |          --- |  -- |
| [0.10, 0.20) |   0 |       --- |          --- |  -- |
| [0.20, 0.30) |   0 |       --- |          --- |  -- |
| [0.30, 0.40) |   0 |       --- |          --- |  -- |
| [0.40, 0.50) |   0 |       --- |          --- |  -- |
| [0.50, 0.60) |  81 |     0.580 |        0.765 | -18.5pp |
| [0.60, 0.70) | 310 |     0.670 |        0.687 | -1.7pp |
| [0.70, 0.80) | 441 |     0.751 |        0.719 | +3.2pp |
| [0.80, 0.90) | 445 |     0.839 |        0.764 | +7.5pp |
| [0.90, 1.00) | 181 |     0.922 |        0.807 | +11.5pp |

## Reliability diagram (after applying fitted calibrator)

| bin           |   N | mean_pred | frac_correct | gap |
|---------------|-----|-----------|--------------|-----|
| [0.00, 0.10) |   4 |     0.000 |        0.750 | -75.0pp |
| [0.10, 0.20) |   0 |       --- |          --- |  -- |
| [0.20, 0.30) |   0 |       --- |          --- |  -- |
| [0.30, 0.40) |   0 |       --- |          --- |  -- |
| [0.40, 0.50) |   0 |       --- |          --- |  -- |
| [0.50, 0.60) |   0 |       --- |          --- |  -- |
| [0.60, 0.70) | 288 |     0.680 |        0.698 | -1.8pp |
| [0.70, 0.80) | 1058 |     0.744 |        0.742 | +0.2pp |
| [0.80, 0.90) |  93 |     0.824 |        0.817 | +0.6pp |
| [0.90, 1.00) |  15 |     1.000 |        0.867 | +13.3pp |

## Fitted breakpoints

```
raw=0.550  ->  calibrated=0.000
raw=0.558  ->  calibrated=0.643
raw=0.677  ->  calibrated=0.698
raw=0.743  ->  calibrated=0.714
raw=0.778  ->  calibrated=0.734
raw=0.839  ->  calibrated=0.774
raw=0.886  ->  calibrated=0.783
raw=0.905  ->  calibrated=0.789
raw=0.930  ->  calibrated=0.818
raw=0.941  ->  calibrated=0.850
raw=0.950  ->  calibrated=1.000
raw=0.980  ->  calibrated=1.000
```

## Decision

- **Propose update?** `True`
- Current live ECE: `0.061`
- New candidate ECE: `0.009`
- ECE drop: `+0.052` (threshold for propose: `0.030`)
- Reason: new ECE 0.009 beats current 0.061 by +0.052
