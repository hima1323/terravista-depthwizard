# Benchmark source

Code behind the DepthWizard model comparison report.

1. `run_models.py <out_dir>` runs RS3DAda, the MambaVision-T student and two Depth Anything V2 models on the same
   750 tiles (GAMUS test + Overhead Geopose ATL / ARG) and caches predictions in `<out_dir>/pred`.
2. `score_results.py <out_dir>` scores them with `SynRS3D/demo/eval_v2.py` and writes `results.json` and `examples.png`.

Run both with `SynRS3D/.venv/bin/python`. Tile lists: `SynRS3D/data/GAMUS_bench.txt` and
`SynRS3D/data/geopose/OGC_*/bench.txt`. The data and weights are not in git.

The published scores come from Song et al. (NeurIPS 2024, arXiv:2406.18151) and Song et al. (arXiv:2505.06905), cited in the report.
Depth Anything V2 relative outputs reach about 480, so `run_models.py` rescales them per tile before saving; both
scripts stop if a model's predictions are clipped or constant.
