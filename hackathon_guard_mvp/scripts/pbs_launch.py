"""Print concrete PBS argv; never submit jobs from this program."""
import shlex
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from guard_mvp.io import cli, entry


def options(p):
    p.add_argument("--stage", choices=("preflight", "pilot", "train", "evaluate"), required=True)
    p.add_argument("--site", default="configs/pbs_site.example.yaml")
    p.add_argument("--condition", choices=("E0", "E1", "E2", "E3"))


def main():
    args, b, c = cli("Print a submission command without submitting", options)
    site = b.read(args.site)
    for k in ("queue", "project", "select", "walltime"):
        if not isinstance(site[k], str) or not site[k].strip():
            raise ValueError("unresolved PBS " + k)
    if args.stage == "evaluate" and not args.condition:
        raise ValueError("evaluation requires --condition")
    # Shell redirects are not relied on: PBS receives explicit confined destinations.
    out = b.path("runs/pbs")
    out.mkdir(parents=True, exist_ok=True)
    tag = args.stage + ("-" + args.condition if args.condition else "")
    variables = f"GUARD_ROOT={b.root}"
    if "," in str(b.root):
        raise ValueError("PBS variable encoding does not support comma in root")
    if args.condition:
        variables += ",GUARD_CONDITION=" + args.condition
    command = ["qsub", "-N", "guard_" + tag, "-q", site["queue"], "-P", site["project"],
               "-l", "select=" + site["select"], "-l", "walltime=" + site["walltime"],
               "-o", str(b.path(out / (tag + ".out"))), "-e", str(b.path(out / (tag + ".err"))),
               "-v", variables, str(b.path("pbs/" + args.stage + ".pbs"))]
    print("cd " + shlex.quote(str(b.root)))
    print(shlex.join(command))
    print("# gpu_free targets the documented H200 pool; allocated GPU name/memory are still verified.")


if __name__ == "__main__":
    entry(main)
