# G06 Top-1 位姿解算与重投影验证报告

## 结论摘要

- 没有 Top-1 策略同时满足 PnP、Layer-2 和 Layer-3 精度阈值。
- 该实验验证的是“已有几何匹配之后只拿 1 个候选做位姿”，不证明可以跳过重排。

## 子组汇总

| subgroup | accepted | PnP ok | best ok | Layer-2 mean m | Layer-2 delta m | Layer-3 RMSE m | Layer-3 delta m | reduced downstream s |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| G06A_g02_roma_inlier_top1 | False | 5 | 5 | 2.288524 | 0.215817 |  |  | 611.464181 |
| G06B_g03_siftgpu_inlier_top1 | False | 5 | 5 | 3.073294 | 1.020234 |  |  | 602.643244 |
| G06C_g03_siftgpu_match_top1 | False | 5 | 5 | 2.053060 | 0.000000 |  |  | 602.692347 |

## Validation Timeout Note

- All three subgroups reached PnP 5/5 ok and produced Layer-2 pose-vs-AT outputs.
- The validation suite timed out during Layer-3 tiepoint evaluation under the 600s per-subgroup limit.
- G06C was retried separately with a 3600s limit and still timed out during evaluate_pose_ortho_tiepoint_ground_error, so its missing Layer-3 value is treated as an operational failure for this Top-1 validation experiment.
