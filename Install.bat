@echo off
rem DepthWizard: one-time setup (Python environment, PyTorch, packages, model weights). Needs internet once.
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0install.ps1"
