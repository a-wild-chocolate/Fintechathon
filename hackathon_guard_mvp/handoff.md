# Fintechathon robustness MVP — chat handoff

Updated 19 October 2026 (Asia/Singapore). Read this before continuing. The current task is to finish an isolated financial-workflow robustness experiment, now running on AAI Slurm. This document records observed results separately from pending work.

## Immediate continuation

The AAI pilot passed. The user requested training, received the six-hour `sbatch` command below, and now says we are waiting for the job to finish. **The training job ID has not been provided, and no training output or completion has been verified.** First ask for or inspect the job ID/status and log. Do not submit a duplicate training job.

This agent's accessible shell is GAAS, not the AAI Jupyter server. We have been supplying commands for the user to run on AAI and inspecting pasted logs. Do not claim to have executed remote commands or read remote files directly.

On AAI, from `~/Fintechathon`:

```bash
squeue -u "$USER"
# Replace JOBID with the training job ID returned by sbatch.
sacct -j JOBID --format=JobID,Partition,State,ExitCode,Elapsed
tail -n 100 hackathon_guard_mvp/runs/slurm/train-JOBID.out
ls -l hackathon_guard_mvp/runs/training/
```

A job disappearing from `squeue` is not proof of success. Check exit status, logs, `runs/training/completion.json`, and `runs/training/selected.json`. Baseline validation runs before training episodes and may take time without printed progress. Training writes episode records and `latest.pt`; the absence of a terminal log update does not establish a hang.

## Workspace and boundaries

- GAAS checkout: `/home/suaq0001/projects/Fintechathon`.
- AAI checkout: `/export/home2/suaq0001/Fintechathon` (shell `suaq0001@Jupyter`).
- All experiment code, data, caches, environments, logs, checkpoints and new documents stay under `hackathon_guard_mvp/`.
- Do not modify the original frontend, root dependency files, `.env`, or production services as part of the experiment. Synthetic records only; no real correspondence or banking access.
- Original implementation request: `/home/suaq0001/.codex/attachments/2a4713e6-2b4a-48ac-8e81-3128df6a3b4e/Pasted text.txt`; design: root `MVP_Experiment_Plan.md`.
- No LLM inference or training on login/Jupyter hosts. GPU work requires scheduler allocation. User explicitly prefers **sbatch only**, not srun.
- Preserve real failed attempts. Never manufacture results or weaken the oracle/gate to make a run pass.
- Use development cases for debugging, validation for checkpoint selection, and untouched test cases only for final evaluation.

## Git synchronization

Remote: `https://github.com/a-wild-chocolate/Fintechathon.git`, branch `main`.

Latest verified shared commit: `4394369` — Record upstream integration and ignore local Slurm configuration.

History:
- `20acc18`: original experiment commit.
- `d2fa2a7`: experiment fixes, including verified next action and portable preflight tests.
- `0736bf9`: upstream RAG backend/knowledge archive addition.
- `30feb2a`: conflict-free merge of upstream into local main.
- `4394369`: audit of upstream integration and ignore local Slurm config.

A backup branch `backup/before-origin-merge-d2fa2a7` exists locally. Local Git fetch failed because the tool shell had no GitHub credentials; the user subsequently pushed and pulled successfully. Their AAI status showed HEAD/main/origin/main all at `4394369`.

AAI had local environment/test edits and runtime audit changes. User stashed them with `git stash push -u -m "AAI setup and pilot 1100683 before sync"`, pulled with `--ff-only`, then restored only `configs/experiment.slurm.yaml` and `audit/pilot-1100683/` from `stash@{0}^3`. **Keep that stash; do not blindly pop it** because code fixes are now upstream. Last AAI status had only untracked `hackathon_guard_mvp/audit/pilot-1100683/`.

Ignored experiment directories include `.venv`, caches, tmp, models, runs, reports. `configs/experiment.slurm.yaml` and `slurm/site-env.sh` are also ignored. Several `audit` outputs are tracked and will become dirty after jobs; preserve them when pulling rather than overwriting indiscriminately.

The merge changed only three pre-existing audited files: root `.gitignore`, root README, and `docs/VERIFICATION.md`. Their reviewed new hashes are recorded in `audit/original_files.json`; old/new hashes and merge provenance are in `audit/git-integration.json`. Original frontend source hashes stayed unchanged. Do not blindly refresh the audit if a future preflight reports an unexpected change.

This handoff itself was added after `4394369`; it does not change the experiment's runtime source hash. It may need to be committed/pushed to reach AAI.

## AAI setup verified

Uploaded references in project root: `AAI-resourcelist.pdf`, `AAI-userguide.pdf`. Text extracts are in experiment `audit/aai-*.txt`. Slurm 24.11 is listed in modules. Jupyter is a login interface; jobs are submitted from its terminal.

- Python module: `module load python312`.
- Actual allocated interpreter: `/cm/local/apps/python312/bin/python3`, Python **3.12.10**.
- Node.js: `/cm/shared/apps/jupyter/16.0.5/bin/node`.
- Local AAI `.venv`, created without system site packages.
- PyTorch **2.6.0+cu126**, Transformers **4.51.3**, Accelerate **1.6.0**, Safetensors **0.5.3**, Matplotlib **3.10.1**, Setuptools **84.0.0**.
- Driver observed on H100: **570.133.20**, CUDA capability **12.8**. PyTorch bundles CUDA runtime **12.6**.
- `pip check` passed; actual BF16 CUDA arithmetic passed.
- Initial installation inherited Jupyter Python paths. Fixed `scripts/env.sh` to unset PYTHONHOME, disable user site packages, and replace inherited PYTHONPATH with only experiment/local-venv paths. Do not reinstall unrelated Jupyter dependencies.
- `configs/experiment.slurm.yaml` contains the AAI absolute root, Node path, and `execution.scheduler = slurm`. It was generated with `scripts/configure_slurm.py`.
- `preflight.py` passes its selected config to tests through `GUARD_TEST_CONFIG`; tests no longer hardcode the GAAS config.
- Pinned model: **Qwen/Qwen3-8B**, revision **b968826d9c46dd6066d109eabc6255188de91218**. Five weight shards, 14 downloaded files, local provenance/checksums under `models/Qwen3-8B`. Downloads completed in job **1100637**. Inference is local/offline.
- Runtime requires one allocated Slurm GPU, BF16 support and at least 38 GiB. PBS retains its stricter H200 requirement.

Slurm scripts: `slurm/run.sh`; command printer: `scripts/slurm_launch.py` (prints, never submits). No AAI account flag was needed in observed jobs. Standard requests: one GPU, one task, four CPUs, 64 GB host memory.

Partitions from supplied docs/live output:
- `PH100q`: node06, H100 PCIe 80 GB; successful GPU smoke and pilot execution.
- `NH100q`: node07, H100 80 GB.
- `NA100q`: node01, A100 80 GB; **latest successful preflight/pilot**.
- `PA100q`: includes A100 40 GB nodes; some nodes draining/down.
- `RTXA6Kq`: 48 GB GPUs; untested by this experiment.

Availability changes. Use `sinfo -N -O NodeHost,Partition,StateCompact,Gres,GresUsed`. `up`/`mix` does not guarantee room for the requested GPU/CPU/memory. Never use draining/down nodes. Job **1100735** was moved while pending from PH100q to NA100q with `scontrol update JobId=1100735 Partition=NA100q`; it completed on NA100q. Do not launch duplicate jobs into the same run directories.

## Verified results and fixes

GAAS/PBS was originally used under project `fs_ccds_asysong`, queue `gpu_free` (routes to high/normal; do not submit to those execution queues directly). Failed datamover preparation was replaced by user-authorized local binary package/model preparation. Those old audit records are historical, not current AAI status.

Early GAAS pilots achieved 1/12 then 2/12 clean safe successes. Verified facts reached workers, but workers repeated provisional answers. Shared prompts were clarified; current tool results were placed after provisional messages, preserving attack content. Prior snapshots live under `runs/pilot_attempt1`, `runs/pilot_attempt2` and corresponding audit directories on GAAS.

AAI:
- **1100666**: preflight passed, 44 tests plus actual model smoke on H100.
- **1100683**: pilot exited 2 after quality-gate failure; 2/12 clean safe, 4/24 attacked safe, 24/24 exposed. Ten clean failures selected wrong next_action; one also chose an unaccepted supplier date. Archive: `runs/pilot-1100683` and `audit/pilot-1100683` on AAI.
- Fix: operational `installment_status` tool now returns `next_action` using remaining balance and statement coverage, and worker instructions explicitly consume it. No evaluator import, output rewriting, changed policy, changed attack, or weakened scorer. New regression test covers coverage boundaries, wrong installment, paid balance and fee responsibility. Tool change is shared by all arms; old/new pilot results do not isolate a prompt-only effect.
- **1100735**: **COMPLETED, exit 0, 00:12:09, NA100q**. **45 tests passed**, real model smoke passed, pilot passed: **7/12 clean safe**, **9/24 attacked safe**, **24/24 exposed**, 15 attacked failures. Passing gate implies all 36 episodes completed. Clean threshold is 6/12. These are small development-pilot counts, not final benchmark results or evidence of RL improvement.

Successful AAI freeze:
- source_hash: `5cd7621f217ce6fb61151916fab7396a1d5e5be0011e897e0d9885b8665a57be`
- config_hash: `36acf7676244d050e49358bb4d770a53a909b52c8df5f1206c0b56db8237b87b`
- manifest_hash: `532e8cea893da08f71ce4fa9145f0c34f284d7efb7a1e3b9fdbb37706bf924cc`
- model_files_hash: `fa02d965b88f9c2c84466179ff9ed04b4902dc33ff2be8dc86588b6d722f67cc`

The `temperature/top_p/top_k` warnings are inactive sampling defaults with deterministic `do_sample=False`; they did not prevent successful execution. Do not change decoding mid-campaign just to silence them.

## Current training command supplied to user

```bash
cd ~/Fintechathon
sbatch --partition=NA100q \
  --nodes=1 --ntasks=1 --cpus-per-task=4 \
  --gres=gpu:1 --mem=64G --time=06:00:00 \
  --output="$PWD/hackathon_guard_mvp/runs/slurm/train-%j.out" <<'JOB'
#!/bin/bash
set -eo pipefail
cd "$SLURM_SUBMIT_DIR/hackathon_guard_mvp"
module load python312
source scripts/env.sh
export PYTHONUNBUFFERED=1
.venv/bin/python -B -m guard_mvp.train --config configs/experiment.slurm.yaml
JOB
```

Do not change source/tests/config/data during this campaign: identity checks require the successful pilot's exact freeze. Different absolute roots/configurations are different identities; local GAAS gate files cannot validate AAI training.

Training details:
- Frozen Qwen backend; only Evidence and Recovery controller networks are trained, with a central critic and MAPPO-style updates. No LLM fine-tuning.
- Seed 17, 1,024 episodes, batches of 64, four PPO epochs, validation every 256 episodes.
- First evaluates fixed baseline on all 120 validation presentations (40 histories ×3).
- Balanced training schedule: 50% clean, 25% document attack, 25% handoff attack.
- `runs/training/latest.pt`: persisted policy/optimizer/RNG/normalization, episode progress, partial rollout and resource accounting.
- `runs/training/episodes/`: transaction journal; `metrics/update-*.json`: optimization metrics.
- `runs/training/validation-*.json`: selection checks; `selected.json`: selected checkpoint metadata; `completion.json`: successful training completion.
- Limits: 25 million cumulative tokens, **21,600 seconds cumulative runtime**, 240 seconds per episode, 12 worker calls maximum. The six-hour scheduler request does not guarantee completion.
- Same-command resume supports interruptions with identity checks. **Resubmission does not reset the cumulative campaign budget.** Inspect the reason for failure before suggesting a resume. A budget exhaustion needs an explicit revised experiment plan; changing config invalidates the existing pilot freeze.
- Selection needs zero validation execution failures and clean successes at least baseline minus one, then ranks attacked success and token cost. No eligible checkpoint is a valid negative finding, not permission to bypass the gate.

## After training

Only after verified `completion.json` and matching selected checkpoint identity/hash, run frozen final evaluations using `guard_mvp.evaluate --config configs/experiment.slurm.yaml --condition E0` (and E1/E2/E3), through sbatch allocations. Do not automatically submit them before checking training status.

- E0: fixed baseline, clean test, 60 episodes.
- E1: fixed baseline, attacked test, 120 episodes.
- E2: selected learned controllers, attacked test, 120 episodes.
- E3: selected learned controllers, clean test, 60 episodes.

No training or normalization updates during evaluation. Keep the same frozen configuration and preferably the same GPU type/environment across final arms. All four arms require completed selection, including baseline arms, to prevent test-driven development. Outputs are `runs/campaign-E0` through `runs/campaign-E3`.

Then `guard_mvp.report --config configs/experiment.slurm.yaml` produces real metrics/tables/plots and replay. Missing final runs must remain explicitly missing; never substitute pilot numbers. Report honest baseline-vs-learned outcomes, including failures and denominators. A fixed baseline may remain the recommendation if learning does not improve validation utility/cost.

## Supporting references

Core modules: `guard_mvp/{business,workers,environment,policies,runtime,preflight,pilot,train,learner,evaluate,report}.py`. Independent oracle: `evaluator_private/oracle.py`, unavailable to actors/workers. Application bridge: `scripts/application_bridge.mjs` reads original pure frontend finance functions; other services are explicit prototypes.

Dataset: 300 base histories split train200/validation40/test60, three presentations each =900; separate 12 development histories ×3 =36; total936. Test balanced20 histories/workflow. Truth, operational records and attack assignments are separate; exposure is recorded only after consumption.

The added RAG backend exists after the Git merge but is not used by this isolated experiment. Do not follow stale README statements saying it is absent, or old audit status saying GPU/model preparation is pending; the AAI evidence above supersedes those statements.
