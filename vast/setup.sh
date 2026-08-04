#!/usr/bin/env bash
# Prepare a vast.ai box for Smart Road training.
#
# Run order matters: the GPU compatibility check comes first and hard-fails,
# because everything after it is wasted money if the card and the PyTorch build
# disagree. We lost three Kaggle runs to exactly that (a Tesla P100's sm_60 is
# below what the stock PyTorch builds for); an RTX 5090 is the opposite risk --
# sm_120 is newer than older PyTorch wheels know about.
set -euo pipefail

echo "=== 1. GPU and PyTorch compatibility ==="
nvidia-smi --query-gpu=name,memory.total,driver_version --format=csv
python -c "
import sys, torch
cap = torch.cuda.get_device_capability(0)
print(f'torch {torch.__version__} | cuda {torch.version.cuda} | {torch.cuda.get_device_name(0)} | sm_{cap[0]}{cap[1]}')
x = torch.randn(512, 512, device='cuda')
r = float((x @ x).sum())
assert r == r, 'matmul produced NaN'
print('cuda matmul OK')
supported = torch.cuda.get_arch_list()
print('torch built for:', supported)
tag = f'sm_{cap[0]}{cap[1]}'
if tag not in supported:
    sys.exit(f'FATAL: this torch has no kernels for {tag}. Upgrade torch or pick another GPU.')
print(f'{tag} is supported')
"

echo
echo "=== 2. Dependencies ==="
pip install -q --upgrade pip
# --no-deps keeps pip from swapping out the image's torch for one that may not
# have kernels for this card.
pip install -q --no-deps ultralytics==8.3.155 ultralytics-thop py-cpuinfo
pip install -q opencv-python-headless pyyaml tqdm pandas matplotlib seaborn psutil requests scipy
python -c "import ultralytics; print('ultralytics', ultralytics.__version__)"

echo
echo "=== 3. Dataset ==="
mkdir -p /workspace && cd /workspace
if [ -f /workspace/data/data.yaml ]; then
  echo "already present, skipping download"
else
  pip install -q kaggle
  mkdir -p ~/.config/kaggle
  : "${KAGGLE_API_TOKEN:?set KAGGLE_API_TOKEN before running}"
  echo "$KAGGLE_API_TOKEN" > ~/.kaggle/access_token 2>/dev/null || {
    mkdir -p ~/.kaggle && echo "$KAGGLE_API_TOKEN" > ~/.kaggle/access_token
  }
  chmod 600 ~/.kaggle/access_token
  kaggle datasets download -d uzbtrust/smartroad-yolo -p /workspace --unzip
  mkdir -p /workspace/data
  # the archive unpacks either flat or under a folder depending on how Kaggle
  # zipped it; normalise both shapes to /workspace/data
  if [ -f /workspace/data.yaml ]; then
    mv /workspace/data.yaml /workspace/images /workspace/labels /workspace/data/ 2>/dev/null || true
  fi
  find /workspace -maxdepth 3 -name data.yaml
fi

python - <<'PY'
from pathlib import Path
root = next(p.parent for p in Path('/workspace').rglob('data.yaml'))
n_tr = len(list((root / 'images/train').glob('*.jpg')))
n_va = len(list((root / 'images/val').glob('*.jpg')))
print(f'dataset at {root}: {n_tr} train / {n_va} val images')
assert n_tr > 30000, f'expected ~41k training images, found {n_tr}'
# rewrite the absolute path baked in on the machine that built the dataset
lines = (root / 'data.yaml').read_text().splitlines()
out = [f'path: {root}' if l.startswith('path:') else l for l in lines]
(root / 'data.yaml').write_text('\n'.join(out) + '\n')
print((root / 'data.yaml').read_text())
PY

echo
echo "=== ready ==="
