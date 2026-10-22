# DepthWizard: teammate guide (22–23 Oct 2026 update)

This guide takes you from a fresh clone to a trained, benchmarked student model. Commands are given for **Windows (PowerShell)**, with Linux/macOS versions where they differ. Every path is relative to the repository root.

## What's new in this update

- **New interface.** There is a Home landing page, a Scenes tab (choose or upload a scene; the six tools open for it), a scene switcher in the top bar, and the Claude Design "field" theme. It's already built into `SynRS3D/web/app/`, so you don't need Node.js unless you change the UI.
- **N5, the ICESat-2 roof-photon filter.** Laser points that NASA labelled "ground" but that sit on a building and more than 3 m above the other ground points are now treated as roofs. They're left out of terrain levelling and terrain checks. This fixed Chandigarh's false 15 m terrain error. Results: `docs/CLAIMS.md` row T8 and `SynRS3D/demo/roof_filter_n5.py`.
- **Student models.** `SynRS3D/train_distill.py` trains a small copy of RS3DAda: a DINOv2 ViT-S/B, or NVIDIA MambaVision. `SynRS3D/export_onnx.py` exports a ViT student to ONNX. Setting `DW_WEIGHTS` makes the app and the benchmarks use a student. Full details: `docs/GPU_TRAINING.md`.
- **Research backlog.** `BRIEF_Claude_Science.md` is the project brief; the feature IDs N1–N16 come from it.

## 1. Clone and install

```powershell
git clone -b oct22-ui-n5-distill https://github.com/hima1323/terravista-depthwizard.git
cd terravista-depthwizard
.\Install.bat        # once: Python env in SynRS3D\.venv, PyTorch (GPU build if you have NVIDIA), the 1.4 GB model, a sample scene
.\DepthWizard.bat    # starts the app at http://127.0.0.1:8000
```

On Linux or macOS, follow *Manual installation* in `docs/TECHNICAL.md`, then run `cd SynRS3D && .venv/bin/python app.py`.

Check before going further:
- [ ] Home, Scenes and all six tools open.
- [ ] Uploading an image works.
- [ ] The scene name in the top bar switches scenes.

If anything looks wrong, take a screenshot and post it in the team chat.

## 2. Pick where to train

| Your machine | Use |
|---|---|
| No NVIDIA GPU | **3A: Kaggle** (free GPU in the browser) |
| NVIDIA GPU with ≥ 8 GB of memory, Windows | **3B** for the ViT-S student. MambaVision doesn't install on Windows: use Kaggle (3A) or WSL2 for it. |
| NVIDIA GPU, Linux / WSL2 | **3B** for both students |

## 3A. Train on Kaggle

1. **Make a read-only GitHub token.** Go to GitHub › Settings › Developer settings › Fine-grained tokens › Generate. Choose *Only select repositories* → `terravista-depthwizard`, with permission *Contents: Read-only*. Copy the token.
2. **Create a Kaggle notebook** with **Accelerator: GPU T4 x2**, **Internet: on** and **Persistence: Files only**. Under *Add-ons › Secrets*, add a secret named `GITHUB_TOKEN` and paste the token.
3. **First cell, replacing Cell 1 of `docs/GPU_TRAINING.md`:**
   ```python
   from kaggle_secrets import UserSecretsClient
   tok = UserSecretsClient().get_secret('GITHUB_TOKEN')
   !git clone -q -b oct22-ui-n5-distill https://{tok}@github.com/hima1323/terravista-depthwizard.git /kaggle/working/repo
   %cd /kaggle/working/repo/SynRS3D
   !pip install -q albumentations rasterio pyproj h5py huggingface_hub
   !df -h /kaggle/working /tmp
   ```
4. **Run Cells 2, 3 and 4A** from `docs/GPU_TRAINING.md`: teacher weights, the 15 GB SynRS3D subset, then the ViT-S student.
   - Watch the first 200 steps: the `min` field shows elapsed minutes.
   - A session lasts at most 12 h. If it ends, re-run the cells and training resumes from the last save.
5. **Do Cell 4B (MambaVision) only after 4A has finished.** Both share the weekly GPU quota of about 30 h.
6. **Download** `student_vits.pth` and `student_vits.pth.log.jsonl` from the notebook's *Output* tab.

## 3B. Train on your own NVIDIA GPU

First, check that PyTorch can see the GPU:
```powershell
cd SynRS3D
.\.venv\Scripts\python.exe -c "import torch; print(torch.cuda.is_available(), torch.cuda.get_device_name(0))"
```
It must print `True` and your GPU name. If it prints `False`, `Install.bat` installed the CPU build. Fix it with:
`.\.venv\Scripts\python.exe -m pip install torch torchvision --index-url https://download.pytorch.org/whl/cu128`

Next, get the training images. Cell 3 of `docs/GPU_TRAINING.md` downloads about 15 GB of zips and needs about 30 GB of free disk. Run it in Python, with `/tmp/synrs3d` changed to a folder on a disk with space, for example `D:/synrs3d`.

Then train:
```powershell
.\.venv\Scripts\python.exe train_distill.py --images D:/synrs3d --student vits --steps 20000 --batch 8 --workers 2 --out pretrain/student_vits.pth
```
- If you get "CUDA out of memory", use `--batch 4`.
- To continue after stopping, re-run the same command: it resumes from `pretrain/student_vits.pth.resume`.

## 4. Benchmark the student

Run this on any machine that has the student in `SynRS3D\pretrain\`. The first run downloads the GAMUS and Geopose test tiles. A GPU makes it much faster: on CPU, budget a few hours.

```powershell
cd SynRS3D
$env:DW_WEIGHTS = "pretrain\student_vits.pth"
.\.venv\Scripts\python.exe demo\gamus_benchmark.py          # 150 GAMUS LiDAR tiles
.\.venv\Scripts\python.exe demo\gamus_v2.py                 # report with 95% CIs
.\.venv\Scripts\python.exe demo\geopose_benchmark.py fetch  # Atlanta / Buenos Aires satellite tiles
.\.venv\Scripts\python.exe demo\geopose_benchmark.py predict
.\.venv\Scripts\python.exe demo\geopose_benchmark.py report
Remove-Item Env:DW_WEIGHTS
```
On Linux or macOS, use `export DW_WEIGHTS=pretrain/student_vits.pth`, `.venv/bin/python`, `/` in paths, and `unset DW_WEIGHTS`.

Results go to `SynRS3D\demo\benchmark\by_weights\student_vits\`, separate from RS3DAda's. Compare them with the teacher: GAMUS MAE 3.90 m [3.24, 4.66], Atlanta 5.99 m, Buenos Aires 1.94 m.

## 5. Export to ONNX (ViT students only)

```powershell
.\.venv\Scripts\python.exe -m pip install onnx onnxruntime
.\.venv\Scripts\python.exe export_onnx.py pretrain\student_vits.pth
```
It prints the ONNX-vs-PyTorch difference, which must be under 0.01, and the CPU time per tile. For reference, ViT-S took 1.9 s and RS3DAda ViT-L 81 s on an M3 Mac.

## 6. Send results back

- **Don't commit `.pth` or `.onnx` files.** They're 100 MB or more, `pretrain/` is git-ignored, and GitHub refuses files over 100 MB. Share them through Google Drive.
- **Zip `SynRS3D\demo\benchmark\by_weights\student_vits\`** (reports and logs, without the `cache` folder) and share it the same way. A new `docs/CLAIMS.md` row is added only from those files.
- **For code changes,** work on your own branch and open a pull request:
  ```powershell
  git switch -c <your-branch>
  git add <files>
  git commit -m "..."
  git push -u origin <your-branch>
  ```

## Rules that keep the numbers honest

- Never train on benchmark images: the GAMUS test tiles, the Overhead Geopose ATL/ARG test tiles and the Indian scenes.
- A student copies the teacher's faults (tall buildings come out 15–18 m too low). It's faster, not more accurate.
- MambaVision runs only on an NVIDIA GPU. It's a research comparison and can't ship in the offline app.
- Any number that goes into the deck or README needs a row in `docs/CLAIMS.md` pointing to the JSON file it came from.
