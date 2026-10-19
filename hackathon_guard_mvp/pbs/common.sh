#!/usr/bin/env bash
set -eo pipefail
: "${PBS_JOBID:?PBS allocation required}"
: "${PBS_O_WORKDIR:?PBS submission directory required}"
: "${GUARD_ROOT:?pass explicit absolute GUARD_ROOT}"
[[ "$GUARD_ROOT" = /* ]] || { echo 'GUARD_ROOT must be absolute' >&2; exit 2; }
guard_resolved=$(cd -- "$GUARD_ROOT" && pwd -P)
[[ "$guard_resolved" = "$(cd -- "$PBS_O_WORKDIR" && pwd -P)" ]] || { echo 'PBS_O_WORKDIR mismatch' >&2; exit 2; }
[[ "$(basename -- "$guard_resolved")" = hackathon_guard_mvp ]] || exit 2
cd "$guard_resolved"
source /etc/profile.d/modules.sh
module load pytorch/2.11.0
source scripts/env.sh
set -u
[[ -x .venv/bin/python ]] || { echo 'Run scripts/bootstrap.sh first' >&2; exit 2; }
[[ "$(hostname)" != hpc-gaas-hn* ]] || { echo 'Refusing login host' >&2; exit 2; }
guard_log_dir="$guard_resolved/runs/pbs/${GUARD_STAGE}-${PBS_JOBID//[^a-zA-Z0-9._-]/_}"
case "$(realpath -m -- "$guard_log_dir")" in "$guard_resolved"/*) ;; *) echo 'Out-of-root job log' >&2; exit 2;; esac
mkdir -p -- "$guard_log_dir"
exec > >(tee "$guard_log_dir/live.log") 2>&1
export PYTHONUNBUFFERED=1
echo "Stage $GUARD_STAGE on $(hostname -s), PBS $PBS_JOBID"
exec .venv/bin/python -B -m "guard_mvp.$GUARD_STAGE" --config configs/experiment.yaml --experiment-root "$guard_resolved" "${guard_args[@]}"
