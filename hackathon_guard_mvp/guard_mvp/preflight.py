"""CPU readiness checks by default. Explicit --gpu requires an allocation."""
import importlib.metadata as metadata
import json
import os
import platform
import subprocess
import sys
from .io import cli, entry
from .validate_data import validate
from .runtime import check_originals, source_hash


def main():
    args, b, c = cli("Check isolation, manifests, hard controls and optional allocated GPU smoke",
                     lambda p: p.add_argument("--gpu", action="store_true"))
    check_originals(b)
    m = validate(b, c)
    packages = {}
    for name in ("torch", "transformers", "accelerate", "safetensors", "matplotlib", "torchrl", "tensordict"):
        try:
            packages[name] = metadata.version(name)
        except metadata.PackageNotFoundError:
            packages[name] = None
    test_environment = dict(os.environ, CUDA_VISIBLE_DEVICES="", GUARD_TEST_CONFIG=os.path.abspath(args.config))
    result = subprocess.run([sys.executable, "-B", "-m", "unittest", "discover", "-s", "tests", "-v"],
                            cwd=b.root, env=test_environment, capture_output=True, text=True, timeout=180)
    b.write("audit/cpu-tests.log", result.stdout + result.stderr)
    report = dict(passed=result.returncode == 0, source_hash=source_hash(b), python=platform.python_version(),
                  libraries=packages, presentations=len(m["entries"]), gpu_stage="not executed",
                  tests_command=[sys.executable, "-B", "-m", "unittest", "discover", "-s", "tests", "-v"],
                  node=c["node"], original_files_unchanged=True)
    b.json("audit/cpu_checks.json", report)
    print(result.stdout + result.stderr)
    if result.returncode:
        raise RuntimeError("hard-control tests failed; see audit/cpu-tests.log")
    if args.gpu:
        from .workers import FrozenWorkers
        workers = FrozenWorkers(b, c)
        row = next(r for r in m["entries"] if r["split"] == "development" and r["surface"] == "clean")
        answer, counts = workers.call("planner", {"task": b.read(row["paths"]["visible"])}, c["seed"], "development", "SMOKE")
        b.json("audit/gpu_smoke.json", dict(passed=True, answer=answer, costs=counts, environment=workers.environment))
        b.write("audit/actual-environment.lock", "\n".join(f"{k}=={v}" for k, v in sorted(workers.environment["libraries"].items())) + "\n")
        print("PASS: actual allocated GPU model smoke; recorded actual package/model versions")
    else:
        print("PASS: CPU checks only. GPU/model readiness remains unexecuted.")
    print(json.dumps({"libraries": packages, "model_revision": c["model"]["revision"]}, indent=2))


if __name__ == "__main__":
    entry(main)
