# CashWeave Guard — isolated robustness MVP

Current execution status: the first two GPU pilots completed all 36 cases but failed the clean-success gate (1/12 and 2/12). Both preflights passed. Results and source/audit snapshots are preserved in `runs/pilot_attempt1`, `runs/pilot_attempt2` and corresponding `audit` directories. Attempt 2 corrected most financial fields, but ten clean failures still requested statements despite complete verified coverage. Attempt 3 adds an explicit next-action decision table and presents current authorized results after provisional context, preserving all attack content. A regression test checks this evidence boundary. Preflight **88551.gaas** and dependent pilot **88552.gaas** have been submitted; validation is pending. Model, data, attacks, policies, scoring and thresholds remain unchanged. No training has started. See `audit/pilot-attempt3-changes.json` and `audit/execution-status.json`. Earlier implementation-only statements below describe the state before preparation.

This folder contains an implemented, CPU-tested experimental harness around TradeX's existing pure financial functions. It is a **synthetic sandbox**, not a production banking integration. No GPU job, live model pilot, training campaign, selected checkpoint, or final performance measurement is implied by the implementation.

All experiment files, environments, caches, fixtures and outputs belong here. The original application is read only. `audit/original_files.json` records SHA-256 hashes of every pre-existing project file; `audit/initial_git_status.txt` records the pre-existing untracked `MVP_Experiment_Plan.md`. `preflight` checks those hashes.

## What exists and what was added

| Component | Discovery / implementation |
|---|---|
| Cash forecast | Existing `../src/finance.js`: `seriesFor`, `enrich`; invoked through the read-only Node bridge. This forecast includes expected receipts and is never treated as a bank ledger. |
| Partial-payment extraction | Existing `../src/partial-payment.js`: parser, validation and proportional forecast; available through the same bridge and exercised in adapter tests. |
| Follow-up reminders | Existing `../src/followups.js`: accepted-state reminder generation; invoked through the bridge. |
| Supplier confirmation | Existing browser-only `applyConfirmedFields` in `../src/app.js`; requires a checked confirmation field. No headless gateway or parameter-bound approval service exists there. |
| Storage / RAG / models | Browser localStorage and a proxy to a separately described `tradex-rag` service. The service, its database, specialist workers, Qwen3.5/DeepSeek configuration and authentication gateway are not implemented in this repository. No service was contacted. |
| Operational financial controls | **Prototype** integer-minor-unit ledger, FX value dates, statement coverage, fee accounting, exact installment matching, version checks, bound supplier approvals and event idempotency in `guard_mvp/business.py`. |
| Live workers | Implemented local Transformers backend with five separate role prompts and one frozen Qwen3-8B model. Experimental backend; not the proposed production stack. Still requires dependencies, weights and an allocated smoke test. |
| Coordination | Fixed verification heuristic and two small independent actor networks, with a centralized critic and current-policy MAPPO rollout collection. Neither arm is a scripted substitute for an LLM baseline. |
| Outputs | Each real outcome records `backend` and `tool_backend`, actual costs, source/trace references, advice harm, blocked proposals and committed violations separately. |

The pure application adapter is enabled in `configs/experiment.yaml`. Node is available read only at the configured VS Code server path (v24.21.0 when inspected); it was absent from PATH. If that editor installation moves, update `node` **before** the live pilot and freeze. An explicit `prototype` configuration is supported; it is never selected silently.

## Local CPU reproduction

From the original project root:

```bash
bash hackathon_guard_mvp/scripts/bootstrap.sh
cd hackathon_guard_mvp
source /etc/profile.d/modules.sh
module load pytorch/2.11.0
source scripts/env.sh
.venv/bin/python -B -m guard_mvp.generate --config configs/experiment.yaml
.venv/bin/python -B -m guard_mvp.validate_data --config configs/experiment.yaml
.venv/bin/python -B -m guard_mvp.preflight --config configs/experiment.yaml
```

The local virtual environment reuses the site's installed PyTorch read only. Bootstrap does not download packages or weights. Config files use JSON syntax, a valid YAML subset, so CPU checks do not need PyYAML. Every entrypoint accepts `--experiment-root /absolute/path/to/hackathon_guard_mvp`; the absolute configured root must match this installation. Traversals and escaping output symlinks are rejected. If moving the entire experiment, update the configured root before running it.

`preflight` runs the hard-control suite and existing JavaScript tests with CUDA hidden, then writes `audit/cpu_checks.json` and `audit/cpu-tests.log`. The small actor tests check gradients and checkpoint/RNG math; they do not train a controller or run an LLM. A changed source/test hash invalidates the pilot's CPU gate. A missing dataset, invalid manifest, failed required check or invalid path returns nonzero.

## Dataset and private evaluator

There are **300 benchmark histories / 900 presentations**: 200/40/60 base histories in train/validation/test. Every history has clean, document and handoff presentations with the same operational state and expected answer. The test set has 20 histories per workflow and 20 attacks per workflow/surface cell. Twelve separately authored development scenarios add 36 presentations and are used only for the pilot. Development is outside the 300-history benchmark.

Histories cover promise-versus-credit, partial receipt, seller/buyer fees, FX availability, older credits already in opening cash, accepted/proposed/hypothetical supplier amendments, incorrect installments, duplicate credits and incomplete statement coverage. The company cash projection includes other orders. FX rates are fixed hypothetical scenario parameters. Histories and correspondence/attack wording are split-isolated. Templates remain a small synthetic family; this is not evidence of real-world representativeness.

`data/manifests/dataset.json` holds assignment hashes; `evaluator_private/data/attack_manifest.json` records each intervention, payload mode and location. Opaque filenames are never passed to workers. Worker-visible filenames and provenance stay the same across paired variants. Source text is the only document intervention; only the content of the document worker's handoff is replaced in the stronger handoff threat model. An inserted message is not counted as exposed until a downstream inference consumes it.

The financial oracle is in `evaluator_private/oracle.py`. Only generation and evaluator-side orchestration import it. Workers receive serialized public state and authorized tool responses. Policies receive observable feature vectors and availability masks. They receive no expected answers, case IDs, partition IDs, attack labels or evaluator-derived action masks. The centralized critic uses the two observable vectors and the active-role indicator; oracle information enters only through terminal training rewards.

These are module/API boundaries for a sandbox of fixed programs, not an OS security boundary against arbitrary hostile Python code. Workers have no shell, filesystem execution, networking, banking or correspondence capability. Each episode constructs fresh operational records, gateway state, tool responses, message history and synthetic clock in memory; only its completed evaluator record is persisted.

## Frozen workers and preparation still required

The configured experimental model is `Qwen/Qwen3-8B` at revision `b968826d9c46dd6066d109eabc6255188de91218`, resolved from the [official model metadata](https://huggingface.co/api/models/Qwen/Qwen3-8B). The [official model card](https://huggingface.co/Qwen/Qwen3-8B) documents its Transformers use and non-thinking mode. This backend uses BF16, deterministic decoding, non-thinking mode, an 8,192-token context ceiling and 320 generated tokens per call. It does not change model identities between conditions.

Installed module metadata was inspected: Python 3.12.13 and torch 2.11.0+cu130. Transformers, accelerate, safetensors and matplotlib were absent in that environment. TorchRL/tensordict were also absent, so the learner uses installed PyTorch's Adam, distributions and autograd directly. `requirements.lock` contains proposed **direct pins only**, not a resolved, tested transitive environment. No successful GPU compatibility claim is made. After a successful allocated model smoke, `audit/actual-environment.lock` records every actual package version, and `audit/gpu_smoke.json` records the model revision, GPU name/memory, CUDA and PBS job ID.

The guide identifies the datamover service for transfers, but external package/model egress details remain unresolved. Use an approved transfer/preparation location; do not infer that the login host is permitted. Once that policy is confirmed, prepare only this local environment and model directory. With approved wheels already copied inside `cache/wheels`, the dependency command is:

```bash
.venv/bin/python -m pip install --no-index --find-links cache/wheels -r requirements.lock
```

Alternatively, use the site's approved package source with the same local interpreter and cache environment. The model preparation command below makes network requests but performs no inference; it must run only where the site permits downloads:

```bash
.venv/bin/python -B scripts/prepare_model.py --config configs/experiment.yaml \
  --site-download-policy-confirmed
```

Model provenance and file checksums are recorded under `models/Qwen3-8B`. Runtime inference is offline and verifies the files; it will not silently download weights or substitute another model. No real model download was executed during implementation.

## PBS preparation and commands

The uploaded `../gaas.pdf` (pages 7–8) identifies **`gpu_free`** as the GPU Free submission queue, with eight H200s on `hpc-gaas-g25`. The user confirms access under project **`fs_ccds_asysong`**. Read-only scheduler inspection confirms that `gpu_free` routes to `gpu_free_high` and `gpu_free_normal`; both execution queues have `from_route_only=True`. **Do not submit directly to `gpu_free_normal`**, as the earlier local-script example suggested. The current Unix group appears in the free-queue ACL. Evidence is saved in `audit/gaas-queues.txt`, `gaas-free-node.txt` and `gaas-groups.txt`.

The guide states a four-hour GPU Free maximum; current scheduler settings advertise one hour for the high-priority queue and six hours for normal. The default remains two hours, within the guide's limit. Requests should stay at or below four hours until the documentation discrepancy is clarified. Current site templates recommend 12 CPUs per GPU, so the existing one-GPU / 12-CPU / 64-GB request is retained. The observed `pytorch/2.11.0` module loads Python 3.12.13 and CUDA 13.1.

Queue routing identifies the documented H200 resource pool, so no invented H200 selector or host pin is needed. The scripts still verify one allocated H200 with at least 110 GiB. Allocation and runtime compatibility remain untested. Scheduler spool files and driver/system logs are not controlled by the experiment.

The guide explicitly prohibits running workloads on the login node (page 3). Perform subsequent test suites, dependency builds, model smoke tests and experiments in allocations. Pages 8 and 12 identify `gpu_datamover` for file transfers; live configuration permits at most four CPUs, zero GPUs and 120 hours there. The referenced detailed datamover guide is not included, so external PyPI/Hugging Face egress and any proxy requirements remain unconfirmed. No download policy has been inferred from queue existence alone.

These commands **print** fully resolved `qsub` commands with explicit local stdout/stderr paths; they do not submit:

```bash
.venv/bin/python -B scripts/pbs_launch.py --stage preflight
.venv/bin/python -B scripts/pbs_launch.py --stage pilot
.venv/bin/python -B scripts/pbs_launch.py --stage train
.venv/bin/python -B scripts/pbs_launch.py --stage evaluate --condition E0
.venv/bin/python -B scripts/pbs_launch.py --stage evaluate --condition E1
.venv/bin/python -B scripts/pbs_launch.py --stage evaluate --condition E2
.venv/bin/python -B scripts/pbs_launch.py --stage evaluate --condition E3
```

Prepared absolute commands are also recorded in `audit/submission-commands.txt`. Submit from this folder, passing `GUARD_ROOT`; the launch scripts check it against `PBS_O_WORKDIR`. GPU submission remains a separate authorized action. Do not submit all stages blindly: run the allocated preflight, inspect the real pilot, then train, then evaluate the frozen selected policy. The two-hour site example may require multiple resumes or a site-approved walltime adjustment after profiling. No runtime forecast is claimed.

Inside an allocation the scripts invoke the specified interfaces:

```bash
python -m guard_mvp.preflight --config configs/experiment.yaml --gpu
python -m guard_mvp.pilot --config configs/experiment.yaml
python -m guard_mvp.train --config configs/experiment.yaml
python -m guard_mvp.evaluate --config configs/experiment.yaml --condition E0
# Repeat evaluate for E1, E2, E3; never train during evaluation.
python -m guard_mvp.report --config configs/experiment.yaml
```

## Learning, freeze and resume

Evidence can verify a bank, agreement, installment or cash claim, reuse a current result, request clarification, or do no new check. Recovery can continue, recompute cash, rerun the relevant frozen specialist once, preserve a dependency, or finalize. Each episode is capped at three alternating cycles and 12 live calls. The fixed baseline verifies the relevant evidence, recomputes, verifies the installment and reruns the specialist before finalizing. No existing check was removed to manufacture baseline failures.

The two actors each have two 128-unit hidden layers. A separate centralized critic estimates shared returns. The implementation follows the clipped PPO objective and complete-episode GAE in [Schulman et al.](https://arxiv.org/abs/1707.06347), the cooperative centralized-critic design of [Yu et al.](https://proceedings.neurips.cc/paper/2022/hash/9c1535a02f0ce079433344e14d910597-Abstract-Datasets_and_Benchmarks.html), and the current-policy collection/update structure in the [official PyTorch MAPPO tutorial](https://docs.pytorch.org/rl/stable/tutorials/multiagent_ppo.html). It is a small reference-based implementation, not an unverified claim to use an installed TorchRL runtime.

The default is seed 17, 1,024 episodes, batches of 64 complete episodes, four PPO epochs, learning rate 3e-4, clip 0.2, gamma 0.99, GAE lambda 0.95, entropy 0.01 and gradient clipping 0.5. The first campaign cannot exceed 3,072 episodes. Configured cumulative token/walltime caps and per-episode budgets also apply. Sampling schedules 50% clean / 50% attacks, balanced across workflows and attack surfaces; repeats are not new independent histories.

Only the active actor's transitions enter its actor loss; old log probabilities and normalized inputs remain fixed throughout each update. Training statistics update normalization only between rollout batches and are checkpointed. Each new rollout uses the current actors and live frozen workers. Exact subcall reuse is allowed only in training and keys include model identity/revision, role, prompt, complete source-state digest, decoder configuration, seed, split and arm. Pilot/validation/final evaluation always call the live workers; caches and memories are not shared across final arms.

The live development gate requires at least 6/12 clean safe completions, all 24 attacked presentations exposed, and no infrastructure failures. It records whether there are learnable failures; a resilient baseline is a valid result. The pilot freezes source/test hashes, config, dataset, original application hashes and model-file provenance. Changing these requires a new pilot; no final test data is used to debug a worker or select a checkpoint.

Training journals each completed episode and persists actors, critic, optimizers, normalization, RNG state, partial rollout, progress and resource totals. Resume checks configuration and policy hashes, consumes a completed journal once, and reconstructs each next episode from pristine state. Checkpoints are validated every 256 episodes and at the end. Selection allows at most one extra clean failure versus the fixed heuristic on 40 validation clean histories, then ranks attacked safe completion and actual token cost. It reports whether RL improves the heuristic; the product recommendation remains the fixed baseline unless validation supports a useful improvement.

E0/E1 use the fixed policy; E2/E3 use the same frozen validation-selected checkpoint. All final arms wait for completed selection. Final evaluation has no updates or normalization changes. Completed results are atomically persisted and reused on resume without duplicate denominators. Failed model parses, budgets and other recorded failures remain visible; there is no selective success-only retry.

## Reporting and implementation limits

Without real E0–E3 files, `report` prints **MISSING RESULTS**, writes `reports/missing-results.txt`, returns exit code 2 and produces no performance charts. With all 360 manifest-covered final episodes, it exports `metrics.json`, `results.csv`, `costs.csv`, attack-breakdown and clean-retention tables, real-data plots and an escaped, local `replay.html` containing all traces. Metrics include raw counts and denominators, all-attempt attacker success and exposure-conditioned attacker success. Zero committed violations must not be attributed to learning when the common gateway blocked the effect.

Implemented components are executable, not placeholder success paths. The local prototype business services are deliberate replacements for absent backend components. **Not yet executed or established:** installed inference stack compatibility, live worker competence/parse reliability, PBS H200 allocation, attack effectiveness, full rollout/update integration on live workers, selected checkpoint quality, or final performance. No trained checkpoint, experiment metric or graph has been fabricated. The small template family, single training seed and simulated tools limit generalization claims.

## AAI Slurm and Jupyter launch path

The uploaded `AAI-userguide.pdf` documents `sbatch`, `srun`, explicit partitions and `--gres=gpu:1`, with four CPU cores per GPU. Its Jupyter section describes a login interface, not an automatic GPU allocation. Use a Jupyter terminal to submit jobs. An ordinary notebook kernel without Slurm GPU allocation is rejected. `AAI-resourcelist.pdf` lists H100 80 GB (`NH100q`, `PH100q`), A100 40/80 GB partitions, and 48 GB GPUs (`RTXA6Kq`). Confirm current availability and access with `sinfo`; the guide's old CUDA examples are not a tested environment for this model.

The existing PBS configuration still requires H200. The explicit Slurm configuration accepts exactly one BF16-capable GPU with at least 38 GiB visible memory. This is an eligibility check, not a verified fit or runtime guarantee; the live preflight and development pilot must pass on AAI. GPU type, memory, CUDA, package versions and scheduler job ID are recorded. Do not mix PBS and AAI results or resume a checkpoint across different configurations.

On AAI, copy the project code needed by the original-file audit plus `hackathon_guard_mvp` code/config/data and `audit/original_files.json`. Keep all experiment writes inside that folder. Use a fresh experiment installation: omit `.venv`, caches, `runs`, old gate/freeze/check artifacts, and temporary files. Transfer pinned `models/Qwen3-8B` with `provenance.json` if allowed, or prepare it there using the existing model preparation script and site-approved downloads. Do not copy the GAAS virtualenv: its system packages and CUDA are site-specific. Preserve original application files for the read-only Node adapter and hash checks.

Create a local `.venv` using AAI's supported Python/PyTorch environment, then install `requirements.lock`. The current requirements do not install PyTorch; an AAI-compatible CUDA PyTorch build is required. Confirm the available modules and driver before choosing one. Put any required module loads in `slurm/site-env.sh` inside the experiment; the launcher sources it before `scripts/env.sh`. No CUDA/module name or AAI account is assumed. Node.js must also be available for the application bridge.

From the target experiment folder, create a new config with the correct local root and Node path:

```bash
python3 -B scripts/configure_slurm.py --node "$(command -v node)"
python3 -B scripts/slurm_launch.py --config configs/experiment.slurm.yaml \
  --stage preflight --partition NH100q
```

The second command **prints**, but does not execute, an `sbatch` command. Choose a partition your account can access; `NH100q` above is a documented example, not a claim of current availability. Add `--account YOUR_AAI_ACCOUNT` only if required by AAI; the GAAS project code is not assumed valid there. Default request: one GPU, four CPUs, 64 GB host memory, one hour. Adjust `--time` and `--mem` to current partition limits.

After submitting preflight, use its numeric job ID as a dependency:

```bash
python3 -B scripts/slurm_launch.py --config configs/experiment.slurm.yaml \
  --stage pilot --partition NH100q --afterok 12345
squeue -u "$USER"
sacct -j 12345 --format=JobID,State,ExitCode,Elapsed
```

Replace `12345` with the real preflight job ID. Logs go to `runs/slurm/<stage>-<jobid>.out` and `.err`. `slurm/run.sh` also works inside a real `srun` GPU allocation, with positional arguments `STAGE CONFIG [CONDITION]`. After a successful current-config pilot, the same command printer supports `--stage train` and `--stage evaluate --condition E0` (E1–E3 likewise). No AAI job has been submitted or run from this session; remote environment compatibility remains unverified.
