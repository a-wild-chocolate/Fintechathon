#!/usr/bin/env bash
# Source this only from the isolated experiment. Do not change parent environments.
guard_root=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd -P)
export GUARD_EXPERIMENT_ROOT="$guard_root"
unset PYTHONHOME
export PYTHONNOUSERSITE=1
export PYTHONPATH="$guard_root"
export PYTHONDONTWRITEBYTECODE=1
export HF_HOME="$guard_root/cache/huggingface"
export HF_HUB_CACHE="$HF_HOME/hub"
export HF_DATASETS_CACHE="$guard_root/cache/datasets"
export TORCH_HOME="$guard_root/cache/torch"
export TORCH_EXTENSIONS_DIR="$guard_root/cache/torch_extensions"
export XDG_CACHE_HOME="$guard_root/cache/xdg"
export PIP_CACHE_DIR="$guard_root/cache/pip"
export UV_CACHE_DIR="$guard_root/cache/uv"
export TRITON_CACHE_DIR="$guard_root/cache/triton"
export CUDA_CACHE_PATH="$guard_root/cache/cuda"
export MPLCONFIGDIR="$guard_root/cache/matplotlib"
export TMPDIR="$guard_root/tmp"
export WANDB_DIR="$guard_root/cache/wandb"
export PYTHONPYCACHEPREFIX="$guard_root/cache/pycache"
export WANDB_MODE=disabled HF_HUB_DISABLE_TELEMETRY=1 DO_NOT_TRACK=1
export HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1 TOKENIZERS_PARALLELISM=false
export OMP_NUM_THREADS=2
for guard_path in "$HF_HUB_CACHE" "$HF_DATASETS_CACHE" "$TORCH_HOME" "$TORCH_EXTENSIONS_DIR" "$XDG_CACHE_HOME" "$PIP_CACHE_DIR" "$UV_CACHE_DIR" "$TRITON_CACHE_DIR" "$CUDA_CACHE_PATH" "$MPLCONFIGDIR" "$TMPDIR" "$WANDB_DIR" "$PYTHONPYCACHEPREFIX"; do
  case "$(realpath -m -- "$guard_path")" in "$guard_root"/*) ;; *) echo 'Out-of-root cache path' >&2; return 2;; esac
  mkdir -p -- "$guard_path"
done
if [[ -x "$guard_root/.venv/bin/python" ]]; then
  guard_packages=$("$guard_root/.venv/bin/python" -B -c 'import sysconfig; print(sysconfig.get_path("purelib"))')
  export PYTHONPATH="$guard_root:$guard_packages"
fi
