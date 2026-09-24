# CBB V1.1.3B — 500-Game Historical Effectiveness Test

Date: 2026-09-24  
Research branch: `research/cbb-historical-500-20260924`

## Evidence source

The test uses untouched historical graded boards from the full archived `CBB_Prediction_Engine_V1_1_3B_Champion(2).zip`, not the smaller Supabase recovery ZIP. The full evidence population contains 920 Grade Eligible + D-I Evaluation Eligible games across 25 dates from 2025-11-15 through 2026-03-18.

The 500-game test is a proportional date-stratified sample across all 25 dates with fixed seed `20260924`. No replacement was used.

Integrity checks across the full 920-game source:
- `V1.1.3 Market Data Used = False` for all 920 games.
- `V1.1.3 Target-Date Results Used = False` for all 920 games.
- `Availability Verified = False` for all 920 games.

## 500-game results

| Metric | V1.0.1 baseline | V1.1.3B | Change |
|---|---:|---:|---:|
| Margin MAE | 9.542 | 9.383 | 0.159 lower |
| Margin RMSE | 12.129 | 11.913 | 0.215 lower |
| Signed margin bias | +2.036 | +0.117 | 1.919 lower absolute bias |
| Median absolute margin error | 7.800 | 7.517 | 0.282 lower |
| Winner accuracy | 72.0% | 72.0% | unchanged |
| Brier score | 0.17919 | 0.17919 | unchanged |
| Log loss | 0.53292 | 0.53292 | unchanged |
| Total-points MAE | 15.424 | 15.424 | unchanged |
| 10-bin home-probability ECE | 0.0300 | 0.0300 | unchanged |

V1.1.3B's paired margin-MAE improvement is 0.159 points. Date-cluster bootstrap with 50,000 replicates gives a 95% interval of approximately [-0.002, 0.367] points. The 500-game subset is therefore directionally favorable but narrowly statistically unresolved at the 95% level.

## Diagnostics

- V1.1.3B had lower date-level MAE on 16 of 25 sampled dates.
- Non-neutral games: 447 games; B improves MAE by 0.182 points.
- Neutral games: 53 games; B worsens MAE by 0.030 points.
- Largest sampled margin improvements occur in baseline-margin buckets 3–6 points (+0.318) and 10–15 points (+0.352).
- Baseline-margin 15+ games worsen slightly (-0.035 points).
- At >=70% model confidence: 275 games, 84.0% actual winner accuracy, 83.8% average confidence.
- At >=80% confidence: 179 games, 86.6% actual accuracy, 88.4% average confidence.
- At >=90% confidence: 68 games, 94.1% actual accuracy, 94.7% average confidence.

## Full-population cross-check

Recomputing all 920 eligible games reproduces the archived untouched-validation results:
- V1.1.3B margin MAE: 9.340
- RMSE: 11.840
- signed bias: -0.063
- winner accuracy: 71.74%
- Brier: 0.17718
- log loss: 0.52489
- baseline V1.0.1 margin MAE: 9.495

On the full 920-game population, the archived date-cluster bootstrap supports B's margin improvement; the previously reported 95% interval for challenger-minus-baseline MAE is approximately [-0.247, -0.080]. The loss of 95% significance in the 500-game sample is consistent with reduced statistical power rather than a reversal of the effect.

## Interpretation

V1.1.3B is primarily a margin/spread calibration improvement. It does not improve the probability layer or projected total relative to V1.0.1 because those surfaces are intentionally retained. The strongest evidence is reduced systematic margin bias and modestly lower absolute/RMS margin error.

The main remaining evidence weakness is availability: none of the 920 validation games had verified availability state. That should remain a separate research target.

## Operational note

The small Supabase recovery artifact `cbb/production/CBB_V1_1_3B_Champion.zip` is not self-contained for cloud execution because it omits the sibling `cbb_engine/` source tree required by `run_cbb_champion.sh`. The full archived champion package contains that tree. This is an artifact-packaging/recovery issue, not a model-validation failure.
