# Completed preparation and submitted GPU checks

The user explicitly authorized login-node package installation and model downloading. Preparation used the existing isolated virtual environment, binary wheels only (`--only-binary=:all: --no-compile`), a lower-priority process, and a single-file model download. No compilation, model loading, LLM inference, actor training or test suite ran on the login node during this preparation.

Installed packages: Transformers 4.51.3, accelerate 1.6.0, safetensors 0.5.3, matplotlib 3.10.1, huggingface-hub 0.36.2, tokenizers 0.21.4. The read-only module supplies torch 2.11.0+cu130. `pip check` passed. `prepared-environment.lock` records installed package metadata; this is not a successful GPU smoke record.

Model: Qwen/Qwen3-8B, revision b968826d9c46dd6066d109eabc6255188de91218. All five weight shards and supporting files were downloaded and SHA-256 checksums stored in `models/Qwen3-8B/provenance.json`. Package and download logs are in `runs/preparation/login/`.

Previously system-held datamover job 88472.gaas was canceled after saving diagnostics so it cannot unexpectedly duplicate preparation. Earlier jobs 88470.gaas and 88471.gaas were already canceled.

Submitted under fs_ccds_asysong via gpu_free:
- 88477.gaas: preflight, one GPU, 12 CPUs, one-hour limit.
- 88478.gaas: 36-presentation pilot, same request, afterok:88477.gaas dependency.

The scheduler routed both jobs to gpu_free_high and changed the requested 64 GB to 250 GB. At the recorded check, preflight was queued for pool capacity and pilot was dependency-held. These are not successful GPU results. The pilot will start only if the allocated preflight (including hard-control tests and actual model smoke) exits successfully. No full training or final evaluation was submitted.

PBS stage scripts now also stream logs inside `runs/pbs/<stage>-<job-id>/live.log` once execution begins. Exact submitted argv are saved in `login-prepared-submissions.json`.
