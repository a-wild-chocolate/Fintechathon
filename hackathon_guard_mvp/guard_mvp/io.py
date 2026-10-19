"""Single filesystem boundary for experiment-controlled reads and writes."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import sys
import tempfile


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False)


def digest(value):
    return hashlib.sha256(canonical(value).encode()).hexdigest()


def file_hash(path):
    h = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


class Boundary:
    def __init__(self, root):
        p = Path(root)
        expected = Path(__file__).resolve().parents[1]
        if not p.is_absolute() or p.resolve() != expected or p.is_symlink():
            raise ValueError("experiment_root must be this installation's absolute hackathon_guard_mvp directory")
        self.root = p.resolve()

    def path(self, name):
        p = Path(name)
        if ".." in p.parts:
            raise ValueError("path traversal rejected")
        p = p if p.is_absolute() else self.root / p
        resolved = p.resolve()
        if resolved != self.root and self.root not in resolved.parents:
            raise ValueError("out-of-root path rejected: " + str(p))
        return resolved

    def write(self, name, data):
        p = self.path(name)
        p.parent.mkdir(parents=True, exist_ok=True)
        self.path(p.parent)
        # Atomic replace: interrupted episodes never publish half a record.
        fd, temp = tempfile.mkstemp(prefix=".pending-", dir=str(p.parent))
        try:
            with os.fdopen(fd, "wb") as f:
                f.write(data.encode() if isinstance(data, str) else data)
                f.flush()
                os.fsync(f.fileno())
            os.replace(temp, self.path(p))
        finally:
            if os.path.exists(temp):
                os.unlink(temp)
        return p

    def json(self, name, obj):
        return self.write(name, json.dumps(obj, indent=2, sort_keys=True, allow_nan=False) + "\n")

    def read(self, name):
        return json.loads(self.path(name).read_text())

    def isolate(self):
        paths = {"HF_HOME": "cache/huggingface", "HF_HUB_CACHE": "cache/huggingface/hub",
                 "HF_DATASETS_CACHE": "cache/datasets", "TORCH_HOME": "cache/torch",
                 "TORCH_EXTENSIONS_DIR": "cache/torch_extensions", "XDG_CACHE_HOME": "cache/xdg",
                 "PIP_CACHE_DIR": "cache/pip", "UV_CACHE_DIR": "cache/uv", "TRITON_CACHE_DIR": "cache/triton",
                 "CUDA_CACHE_PATH": "cache/cuda", "MPLCONFIGDIR": "cache/matplotlib",
                 "TMPDIR": "tmp", "WANDB_DIR": "cache/wandb", "PYTHONPYCACHEPREFIX": "cache/pycache"}
        for key, value in paths.items():
            p = self.path(value)
            p.mkdir(parents=True, exist_ok=True)
            os.environ[key] = str(p)
        tempfile.tempdir = str(self.path("tmp"))
        os.environ.update(WANDB_MODE="disabled", HF_HUB_DISABLE_TELEMETRY="1",
                          DO_NOT_TRACK="1", HF_HUB_OFFLINE="1", TRANSFORMERS_OFFLINE="1",
                          PYTHONDONTWRITEBYTECODE="1", TOKENIZERS_PARALLELISM="false")
        sys.dont_write_bytecode = True


def load_config(filename, experiment_root=None):
    # JSON is a strict subset of YAML; avoids a bootstrap dependency.
    expected = Path(__file__).resolve().parents[1]
    b = Boundary(experiment_root or str(expected))
    c = b.read(b.path(Path(filename).absolute()))
    if c.get("experiment_root") != str(b.root):
        raise ValueError("configuration experiment_root mismatch")
    if c.get("schema_version") != 1:
        raise ValueError("unsupported configuration schema")
    for field in ("data_dir", "private_dir", "runs_dir", "reports_dir", "model_dir", "checkpoint"):
        b.path(c[field])
    if c["backend"] not in ("prototype", "application_adapter"):
        raise ValueError("declare a business backend explicitly")
    if not re.fullmatch(r"[0-9a-f]{40}", c["model"]["revision"]):
        raise ValueError("model revision must be an exact commit")
    if c["model"]["id"] != "Qwen/Qwen3-8B":
        raise ValueError("this frozen backend is Qwen/Qwen3-8B")
    d = c["model"]["decoding"]
    if d["do_sample"] is not False or d["enable_thinking"] is not False or not 1 <= d["max_new_tokens"] <= 512 or not 512 <= d["context_limit"] <= 8192:
        raise ValueError("unsupported frozen decoding settings")
    if not re.fullmatch(r"[A-Za-z0-9_-]+", c["run_prefix"]):
        raise ValueError("invalid run prefix")
    t = c["training"]
    if any(type(t[k]) is not int for k in ("episodes", "batch_episodes", "epochs", "validate_every")):
        raise ValueError("training counts must be integers")
    if not 1 <= t["episodes"] <= 3072 or not 1 <= t["batch_episodes"] <= 64:
        raise ValueError("training episode bounds exceeded")
    if not 1 <= t["epochs"] <= 10 or not 1 <= t["validate_every"] <= t["episodes"]:
        raise ValueError("invalid bounded update/validation schedule")
    if not 0 < t["lr"] <= .01 or not 0 < t["clip"] < 1 or not 0 < t["gamma"] <= 1 or not 0 <= t["gae_lambda"] <= 1:
        raise ValueError("invalid PPO configuration")
    if c["limits"]["cycles"] != 3 or not 1 <= c["limits"]["llm_calls"] <= 12:
        raise ValueError("episode resource bounds exceeded")
    for k in ("tokens", "wall_seconds", "episode_seconds"):
        if c["limits"][k] <= 0:
            raise ValueError("resource limits must be positive")
    b.isolate()
    return b, c


def cli(description, extra=None):
    p = argparse.ArgumentParser(description=description)
    p.add_argument("--config", default="configs/experiment.yaml")
    p.add_argument("--experiment-root")
    if extra:
        extra(p)
    args = p.parse_args()
    b, c = load_config(args.config, args.experiment_root)
    return args, b, c


def entry(fn):
    try:
        fn()
    except (ValueError, FileNotFoundError, RuntimeError, ImportError, PermissionError) as e:
        print(f"FAILED: {type(e).__name__}: {e}", file=sys.stderr)
        raise SystemExit(2)
