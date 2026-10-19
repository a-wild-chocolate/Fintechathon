#!/usr/bin/env bash
set -eo pipefail
source /etc/profile.d/modules.sh
module load pytorch/2.11.0
source "$(dirname -- "$0")/env.sh"
set -u
cd "$GUARD_EXPERIMENT_ROOT"
case "$(realpath -m .venv)" in "$GUARD_EXPERIMENT_ROOT"/*) ;; *) echo 'Escaping virtual environment path' >&2; exit 2;; esac
if [[ ! -x .venv/bin/python ]]; then
  python -B -m venv --system-site-packages .venv
fi
source scripts/env.sh
echo 'Local virtual environment prepared; no packages or model weights downloaded.'
