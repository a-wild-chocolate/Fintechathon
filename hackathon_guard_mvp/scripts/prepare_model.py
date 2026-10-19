"""Explicit local preparation only after confirming the site's download policy."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from guard_mvp.io import cli, entry, file_hash


def main():
    args, b, c = cli("Prepare pinned Qwen weights in the isolated folder",
                     lambda p: p.add_argument("--site-download-policy-confirmed", action="store_true"))
    if not args.site_download_policy_confirmed:
        raise RuntimeError("site download policy is unresolved; confirm permitted host/network before preparing weights")
    import os
    os.environ["HF_HUB_OFFLINE"] = "0"
    os.environ["TRANSFORMERS_OFFLINE"] = "0"
    from huggingface_hub import snapshot_download
    target = b.path(c["model_dir"])
    target.mkdir(parents=True, exist_ok=True)
    for existing in target.rglob("*"):
        b.path(existing)
    snapshot_download(c["model"]["id"], revision=c["model"]["revision"], local_dir=str(target),
                      cache_dir=str(b.path("cache/huggingface/hub")),
                      max_workers=1,
                      allow_patterns=["*.json", "*.safetensors", "*.txt", "LICENSE", "README.md"])
    files = {str(p.relative_to(target)): file_hash(b.path(p)) for p in target.rglob("*") if p.is_file()
             and ".cache" not in p.parts and p.name != "provenance.json"}
    if not any(name.endswith(".safetensors") for name in files):
        raise RuntimeError("no model weights prepared")
    b.json(target / "provenance.json", dict(id=c["model"]["id"], revision=c["model"]["revision"], files=files))
    print("Pinned files prepared; no inference performed. Allocated smoke still required.")


if __name__ == "__main__":
    entry(main)
