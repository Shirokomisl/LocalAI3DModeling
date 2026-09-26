$ErrorActionPreference="Continue"
Write-Host "=== Local 3D Agent diagnostics ==="
nvidia-smi --query-gpu=name,memory.total,driver_version --format=csv,noheader
ollama --version
ollama list
opencode --version
$py="C:\AI\Hunyuan3D-2.1\.venv\Scripts\python.exe"
& $py -c "import torch; print('torch',torch.__version__); print('cuda',torch.cuda.is_available()); print('gpu',torch.cuda.get_device_name(0) if torch.cuda.is_available() else 'none')"
& $py -c "import sys; sys.path.insert(0,'C:\AI\Hunyuan3D-2.1\hy3dshape'); import hy3dshape; import timm; print('Hunyuan Python package: OK'); print('timm',timm.__version__)"
if(Test-Path 'C:\AI\Hunyuan3D-2.1\hunyuan3d-dit-v2-1\model.fp16.ckpt'){ Write-Host 'Shape checkpoint: OK' } else { Write-Warning 'Shape checkpoint missing' }
opencode models ollama
Write-Host "=== end ==="
