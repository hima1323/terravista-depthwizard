# Training on a free GPU (Kaggle or Colab)

This guide covers two runs that need an NVIDIA GPU, so they can't run on the team's laptops:

| Run | What it gives | Ships in the app? |
|---|---|---|
| **A. Distil RS3DAda into ViT-S** (`train_distill.py --student vits`) | A model about 12× smaller and about 40× faster on CPU (1.9 s vs 81 s per 4-flip tile on an M3), exportable to ONNX | Yes, if its benchmarks hold up |
| **B. MambaVision student** (`train_distill.py --student nvidia/MambaVision-T-1K`) | A Mamba-based model with the same two heads, as a research comparison | No: Mamba layers are CUDA-only, so it can't run on CPU or Mac, or export to ONNX |
| C. MambaVision with the full RS3DAda recipe (`train_dpt_RS3DAda.py --encoder nvidia/MambaVision-T-1K`) | The paper's full domain adaptation, but with a Mamba encoder | No (CUDA-only); needs all 95 GB of SynRS3D plus the real target sets, which is too much for free tiers |

**Students copy the teacher, including its faults.** Tall objects come out about 15–18 m too low. Distillation buys speed, not accuracy. `--gt_weight 0.5` also fits SynRS3D's own height labels. That may reduce the bias, but it's a separate experiment to measure.

**Never train on benchmark images.** Keep the GAMUS test tiles, the Overhead Geopose ATL / ARG test tiles and the Indian scenes out of `--images`.

## 1. Get the code onto Kaggle (once)

The GitHub repository is private. **Either** clone it inside the notebook with a read-only token (see `TEAMMATE_GUIDE.md`, step 3A), **or** upload the code as a private Kaggle dataset. On a Mac or Linux machine, run:

```bash
cd "/Users/prince_13/Documents/iit/sem5/hs202/untitled folder"
zip -r depthwizard_code.zip SynRS3D -x 'SynRS3D/.venv/*' 'SynRS3D/data/*' 'SynRS3D/pretrain/*' \
  'SynRS3D/demo/*' 'SynRS3D/frontend/*' 'SynRS3D/web/*' 'SynRS3D/figs/*' '*/__pycache__/*'
```

Then, on Kaggle: **Datasets › New dataset**, upload `depthwizard_code.zip`, set it to *Private*, and name it `depthwizard-code`.

## 2. Notebook settings

Create a new notebook and set **Accelerator: GPU T4 x2** (or P100), **Internet: on** and **Persistence: Files only**. Add the `depthwizard-code` dataset as an input.

Limits: a Kaggle session lasts at most 12 h and the GPU quota is about 30 h a week. The scripts save every 1,000 steps and resume automatically, so when a session ends you re-run the same cells.

## 3. Cells

**Cell 1: set up and check the disk.**

```python
!cp -r /kaggle/input/depthwizard-code/SynRS3D /kaggle/working/ 2>/dev/null || (cd /kaggle/working && unzip -q /kaggle/input/depthwizard-code/depthwizard_code.zip)
%cd /kaggle/working/SynRS3D
!pip install -q albumentations rasterio pyproj h5py huggingface_hub
!df -h /kaggle/working /tmp   # SynRS3D goes to /tmp: check it has ~40 GB free
```

**Cell 2: teacher weights (1.4 GB).**

```python
from huggingface_hub import hf_hub_download
hf_hub_download('JTRNEO/RS3DAda', 'RS3DAda_vitl_DPT_height.pth', local_dir='pretrain')
```

**Cell 3: a 15 GB subset of SynRS3D.** It covers all three ground resolutions (0.05 / 0.5 / 1 m) and both city types. Each zip is downloaded, unzipped and deleted in turn, so the disk peak stays low.

```python
import os, zipfile
from huggingface_hub import hf_hub_download
SUBSETS = ['terrain_g005_mid_v1', 'terrain_g005_high_v1', 'terrain_g05_mid_v1', 'terrain_g05_high_v1',
           'terrain_g1_mid_v1', 'terrain_g1_high_v1', 'grid_g005_low_v1']          # ~15 GB zipped
os.makedirs('/tmp/synrs3d', exist_ok=True)
for s in SUBSETS:
    if os.path.isdir(f'/tmp/synrs3d/{s}'):
        continue
    z = hf_hub_download('JTRNEO/SynRS3D', f'SynRS3D/{s}.zip', repo_type='dataset', local_dir='/tmp/dl')
    zipfile.ZipFile(z).extractall('/tmp/synrs3d')
    os.remove(z)
    print(s, 'ok')
!find /tmp/synrs3d -path '*/opt/*.tif' | wc -l
```

If the last line prints 0, the zips use a different folder layout. List one of them with `!find /tmp/synrs3d | head` and pass a matching `--pattern` to the training command.

**Cell 4A: distil the ViT-S student.**

```python
!python train_distill.py --images /tmp/synrs3d --student vits --steps 20000 --batch 8 \
    --out /kaggle/working/student_vits.pth
```

Watch the first 200 steps. The `min` field shows elapsed minutes, so estimate the total time from it. If 20,000 steps won't fit, lower `--steps`: the schedule follows it. `val_mae_vs_teacher_m` is how far the student is from the teacher in metres. It's a training signal, not accuracy against real heights.

**Cell 4B: the MambaVision student.** These packages compile CUDA code, so installing them can take a while.

```python
!pip install -q transformers timm einops causal-conv1d mamba-ssm --no-build-isolation
!python train_distill.py --images /tmp/synrs3d --student nvidia/MambaVision-T-1K --steps 20000 --batch 8 \
    --out /kaggle/working/student_mambavision_t.pth
```

If `mamba-ssm` fails to build, install the prebuilt wheel that matches the notebook's torch, CUDA and Python versions from the `state-spaces/mamba` GitHub releases page, and then `causal-conv1d` the same way.

**Download the results.** Use the notebook's *Output* tab, or zip `/kaggle/working/*.pth` together with the `*.log.jsonl` files.

## 4. Back on the Mac: benchmark the student exactly like the teacher

Put the `.pth` file in `SynRS3D/pretrain/`. The `DW_WEIGHTS` setting makes the benchmarks and the app load it. Its predictions and reports go to `demo/benchmark/by_weights/<name>/`, so RS3DAda's cached results are never overwritten.

```bash
cd SynRS3D
export DW_WEIGHTS=pretrain/student_vits.pth
.venv/bin/python demo/gamus_benchmark.py            # downloads (first time) and predicts the 150 GAMUS test tiles
.venv/bin/python demo/gamus_v2.py                   # v2 report with 95% CIs -> demo/benchmark/by_weights/student_vits/v2/
.venv/bin/python demo/geopose_benchmark.py fetch    # Atlanta / Buenos Aires satellite tiles (first time)
.venv/bin/python demo/geopose_benchmark.py predict
.venv/bin/python demo/geopose_benchmark.py report
unset DW_WEIGHTS
.venv/bin/python -m pip install onnx onnxruntime    # once, only for exporting
.venv/bin/python export_onnx.py pretrain/student_vits.pth                      # ONNX + parity check + CPU time
DW_WEIGHTS=pretrain/student_vits.pth .venv/bin/python app.py                                 # try it in the app
```

Benchmark MambaVision students on the Kaggle GPU instead. Copy `data/GAMUS` up as another dataset and run the same commands there.

**Which student ships.** Compare it with RS3DAda (GAMUS MAE 3.90 m [3.24, 4.66], ATL 5.99 m, ARG 1.94 m) using the same v2 protocol. A student is worth shipping as the CPU default only if its confidence intervals overlap the teacher's. Record the result as a new row in `docs/CLAIMS.md` before anything mentions it.

## Run C (full recipe): what it needs

`train_dpt_RS3DAda.py` now accepts `--encoder nvidia/MambaVision-T-1K` (with `--crop_size 384` or `512`, and without `--feat_loss`, which only applies to DINOv2). Use `RS3DAda.sh` with those three changes. A real run needs:
- all 17 SynRS3D subsets (95 GB zipped);
- the authors' preprocessed real target sets (`--tgt_datasets`);
- tens of GPU-hours.

That's beyond the free tiers. A university or paid GPU with about 200 GB of disk is the realistic home for it. The `--learning_rate 1e-6` setting was tuned for ViT-L, so a MambaVision run will probably need a learning-rate sweep.
