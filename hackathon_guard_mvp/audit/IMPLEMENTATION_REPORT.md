# Implementation and verification record

> Site configuration update: the uploaded `gaas.pdf` and live scheduler inspection supersede the original PBS discovery below. Submit to `gpu_free`, not the route-only `gpu_free_normal`; project `fs_ccds_asysong` is user-confirmed. See `GAAS_REVIEW.md` and regenerated `submission-commands.txt`. Original implementation test results below are historical; no workload tests or GPU jobs ran for this documentation/configuration update.

All new experiment artifacts are under `/home/suaq0001/projects/Fintechathon/hackathon_guard_mvp`. All 29 pre-existing project-file hashes match the initial snapshot. The pre-existing dirty item was the untracked `MVP_Experiment_Plan.md`; it is unchanged. Root source, dependency files, `.gitignore`, application state and external scheduler files were not edited.

## Implemented artifacts

- `guard_mvp/`: all requested CLI modules; validated path/config I/O; dataset generation/validation; read-only application adapter; prototype operational financial gateway; isolated headless episodes; frozen local model workers; fixed baseline; two-actor/shared-critic MAPPO; checkpoint/episode resume; validation selection; frozen final evaluation; actual-result reporting.
- `evaluator_private/`: independent financial oracle, private expected answers and attack assignment records. Actor/worker/observation modules do not import it.
- `data/`: 900 grouped benchmark presentations (200/40/60 histories) plus 36 presentations from 12 separate development scenarios. Final grid: 20 histories per workflow, 20 attacks per workflow/surface cell. Manifest SHA-256: `532e8cea893da08f71ce4fa9145f0c34f284d7efb7a1e3b9fdbb37706bf924cc`.
- `configs/`, `scripts/`, `pbs/`: explicit absolute experiment root; model commit pin; local virtual environment/bootstrap; opt-in policy-confirmed weight preparation; read-only JS bridge; four PBS stages and non-submitting command renderer.
- `tests/`, `audit/`, `reports/missing-results.txt`: tests, original and generated-file inventory, real verification logs, prepared commands and explicit missing-results notice.
- `.venv/`, `cache/`, `tmp/`: local environment and cache isolation. No pretrained model files or trained checkpoints were created.

The actual application adapter calls existing pure cash forecast, payment parsing and follow-up functions. Missing authoritative ledger, approval, installment closure and specialist backend services are explicit prototypes/experimental implementations. There are no placeholder-success entrypoints. Live inference, full learner integration, selected checkpoint and final chart/replay export have not been exercised with actual workers.

## Commands actually executed and outcomes

1. `bash scripts/bootstrap.sh`: created local Python 3.12.13 virtual environment, reusing site PyTorch read only; no dependency/model downloads.
2. `.venv/bin/python -B -m guard_mvp.generate --config configs/experiment.yaml`: generated 936 presentations. Unfrozen initial fixtures were rebuilt once while correcting split-specific attack wording.
3. `.venv/bin/python -B -m guard_mvp.validate_data --config configs/experiment.yaml`: passed manifest hashes, pairing, counts and final grid checks.
4. `.venv/bin/python -B -m guard_mvp.preflight --config configs/experiment.yaml`: final pass ran **38 Python tests, 0 failures**, including the Node application tests. See `cpu-tests.log` and `cpu_checks.json`. Earlier implementation passes also passed; the suite was expanded during review.
5. Configured Node v24.21.0 with `--test tests/followups.test.js tests/partial-payment.test.js` from the original project: **10 tests passed, 0 failures**; log `application-tests.log`.
6. AST parsing for every new Python source and `bash -n` for all shell/PBS scripts: passed.
7. `python -m guard_mvp.report --config configs/experiment.yaml`: expected exit 2 with `MISSING RESULTS: E0, E1, E2, E3`; no performance charts produced.
8. `python -m guard_mvp.train ...` and `python -m guard_mvp.evaluate ... --condition E0`: expected exit 2 at missing live-pilot gate; no workers/training started. Exact invocations and outputs are in `entrypoint-checks.json`.
9. `scripts/pbs_launch.py` for preflight/pilot/train/E0/E1/E2/E3: printed seven fully resolved qsub commands to `submission-commands.txt`; **none was submitted**.
10. Final original-file hash verification and empty tracked `git diff`: passed.

The installed CUDA-enabled PyTorch emitted a CUDA-initialization warning during a CPU autograd unit test, then used zero available devices. Tests passed; this is not a successful GPU smoke test. No LLM inference, campaign training, GPU allocation or system-package installation ran on the login host.

## Remaining preparation and unexecuted gates

- Installed/read-only: Python 3.12.13, torch 2.11.0+cu130, Node v24.21.0.
- Missing: Transformers, accelerate, safetensors, matplotlib and pinned Qwen3-8B weights. TorchRL/tensordict are absent and optional: this learner uses PyTorch Adam/distributions directly, following the cited official PPO/MAPPO references.
- `requirements.lock` is a proposed direct-pin list, not a verified transitive lock. Actual full package/model/GPU versions will be recorded after an allocated successful smoke test.
- Model: Qwen/Qwen3-8B at `b968826d9c46dd6066d109eabc6255188de91218`, explicitly experimental, never substituted for the proposed production stack.
- Site evidence resolves example queue `gpu_free_normal`, project `fs_ccds_asysong`, one GPU / 12 CPUs / 64 GB, two-hour walltime, module `pytorch/2.11.0` (loads Python 3.12.13 and CUDA 13.1). These come from existing local PBS scripts, not a new successful allocation.
- Unresolved: permitted download location/network, guaranteed scheduler H200 selector, current queue entitlement/walltime policy. Runtime checks enforce an actual full H200; a generic GPU allocation can fail those checks.
- Unexecuted: allocated model smoke, 12-clean/24-attacked live pilot, bounded live MAPPO campaign, validation selection, final E0–E3, real metrics/plots/replays.

No performance values, completed experiments, trained checkpoints or successful GPU tests are claimed. Follow README preparation, then the exact commands in `submission-commands.txt` in gated order. GPU submission requires separate authorization under the user's request.
