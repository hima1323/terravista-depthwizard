# DepthWizard installer for Windows.
# Sets up everything the app needs in SynRS3D\.venv and SynRS3D\pretrain, after which it runs offline:
#   Python environment -> PyTorch (GPU build if an NVIDIA card is present, CPU build otherwise) -> packages ->
#   model weights (RS3DAda, 1.5 GB) -> DINOv2 model code -> a sample scene -> self-checks.
# Run it with Install.bat (double-click). Safe to run again: finished steps are skipped. -NoPause: no prompt at the end.
param([switch]$NoPause)
$ErrorActionPreference = 'Continue'   # native tools (pip) write warnings to stderr; failures are caught via exit codes
$root = Split-Path -Parent $MyInvocation.MyCommand.Path
$app = Join-Path $root 'SynRS3D'
Set-Location $app
function Step($msg) { Write-Host "`n== $msg" -ForegroundColor Cyan }
function Fail($msg) { Write-Host $msg -ForegroundColor Red; if (-not $NoPause) { Read-Host 'Press Enter to close' }; exit 1 }

Step 'Python 3.10 or newer'
$py = $null
if (Get-Command py -ErrorAction SilentlyContinue) {
    $v = & py -3 --version 2>&1
    if ("$v" -match 'Python 3\.(\d+)' -and [int]$Matches[1] -ge 10) { $py = @('py', '-3') }
}
if (-not $py -and (Get-Command python -ErrorAction SilentlyContinue)) {
    $v = & python --version 2>&1
    if ("$v" -match 'Python 3\.(\d+)' -and [int]$Matches[1] -ge 10) { $py = @('python') }
}
if (-not $py) { Fail 'Python 3.10+ not found. Install it from https://www.python.org/downloads/ (tick "Add python.exe to PATH"), then run Install.bat again.' }
$pyArgs = @($py | Select-Object -Skip 1)
Write-Host "using: $(& $py[0] @pyArgs --version 2>&1)"

Step 'Python environment (SynRS3D\.venv)'
$vpy = Join-Path $app '.venv\Scripts\python.exe'
if (-not (Test-Path $vpy)) { & $py[0] @pyArgs -m venv .venv }
& $vpy -m pip install --upgrade pip --quiet

Step 'PyTorch'
$hasTorch = (& $vpy -c "import importlib.util as u; print(u.find_spec('torch') is not None)") -eq 'True'
if ($hasTorch) { Write-Host 'already installed' }
else {
    if (Get-Command nvidia-smi -ErrorAction SilentlyContinue) { $idx = 'https://download.pytorch.org/whl/cu128'; Write-Host 'NVIDIA GPU found: installing the CUDA build (about 3 GB)' }
    else { $idx = 'https://download.pytorch.org/whl/cpu'; Write-Host 'No NVIDIA GPU: installing the CPU build (slower inference, about 4-6 min per 1024 x 1024 image)' }
    & $vpy -m pip install torch torchvision --index-url $idx
    if ($LASTEXITCODE) { Fail 'PyTorch install failed (see above).' }
}

Step 'Packages (requirements.txt)'
& $vpy -m pip install -r requirements.txt
if ($LASTEXITCODE) { Fail 'Package install failed (see above).' }

Step 'Model weights (RS3DAda, 1.5 GB)'
if (Test-Path 'pretrain\RS3DAda_vitl_DPT_height.pth') { Write-Host 'already downloaded' }
else {
    & $vpy -c "from huggingface_hub import hf_hub_download; hf_hub_download('JTRNEO/RS3DAda', 'RS3DAda_vitl_DPT_height.pth', local_dir='pretrain')"
    if ($LASTEXITCODE) { Fail 'Weight download failed (internet?).' }
}

Step 'DINOv2 model code (kept in pretrain\dinov2 so the app starts offline)'
if (Test-Path 'pretrain\dinov2\hubconf.py') { Write-Host 'already there' }
else {
    & $vpy -c "import os, shutil, torch; torch.hub.load('facebookresearch/dinov2', 'dinov2_vitl14', pretrained=False, trust_repo=True); shutil.copytree(os.path.join(torch.hub.get_dir(), 'facebookresearch_dinov2_main'), os.path.join('pretrain', 'dinov2'), dirs_exist_ok=True)"
    if ($LASTEXITCODE) { Fail 'DINOv2 download failed (internet?).' }
}

Step 'Sample scene'
New-Item -ItemType Directory -Force 'demo\samples' | Out-Null
if (Get-ChildItem 'demo\samples' -File -ErrorAction SilentlyContinue) { Write-Host 'scenes already present' }
else { & $vpy demo\fetch_scene.py chandigarh_sector17 30.7398 76.7827 }

Step 'Self-checks'
& $vpy validate.py
& $vpy terrain.py
& $vpy -c "import torch; d = 'CUDA GPU (' + torch.cuda.get_device_name(0) + ')' if torch.cuda.is_available() else 'CPU'; print('model will run on:', d)"

Write-Host "`nDepthWizard is installed. Start it with DepthWizard.bat." -ForegroundColor Green
if (-not $NoPause) { Read-Host 'Press Enter to close' }
