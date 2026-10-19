#!/usr/bin/env bash
set -eo pipefail
: "${SLURM_JOB_ID:?Submit with sbatch or srun}"
: "${SLURM_JOB_NODELIST:?GPU allocation required}"
guard_root=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd -P)
cd "$guard_root"
guard_stage=${1:?stage required}
guard_config=${2:?config required}
guard_condition=${3:-}
case "$guard_stage" in preflight|pilot|train|evaluate) ;; *) exit 2;; esac
# Site-specific module loads belong in this local, user-reviewed file.
if [[ -f slurm/site-env.sh ]]; then source slurm/site-env.sh; fi
source scripts/env.sh
set -u
[[ -x .venv/bin/python ]] || { echo 'Create a local AAI-compatible .venv first' >&2; exit 2; }
guard_args=()
if [[ "$guard_stage" = preflight ]]; then guard_args+=(--gpu); fi
if [[ "$guard_stage" = evaluate ]]; then
  case "$guard_condition" in E0|E1|E2|E3) ;; *) exit 2;; esac
  guard_args+=(--condition "$guard_condition")
fi
export PYTHONUNBUFFERED=1
exec .venv/bin/python -B -m "guard_mvp.$guard_stage" --config "$guard_config" --experiment-root "$guard_root" "${guard_args[@]}"
