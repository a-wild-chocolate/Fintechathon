from .io import cli, entry, file_hash
from .validate_data import validate
from .runtime import require_pilot, identity, load_checkpoint, evaluate_rows
from .policies import Baseline
from .workers import FrozenWorkers


def main():
    args, b, c = cli("Frozen final evaluation; no updates or test-set selection",
                     lambda p: p.add_argument("--condition", required=True, choices=("E0", "E1", "E2", "E3")))
    m = validate(b, c)
    require_pilot(b, c, m)
    # All four final arms require completed selection so test outcomes cannot
    # guide pilot development or checkpoint selection.
    selected = b.read(c["checkpoint"])
    completion = b.read("runs/training/completion.json")
    if completion["identity"] != identity(b, c, m) or selected["identity"] != identity(b, c, m):
        raise ValueError("final evaluation freeze mismatch")
    if file_hash(b.path(selected["path"])) != selected["sha256"]:
        raise ValueError("selected checkpoint checksum mismatch")
    workers = FrozenWorkers(b, c)
    if args.condition in ("E2", "E3"):
        from .learner import MAPPO
        policy = MAPPO(c["training"])
        policy.load_state_dict(load_checkpoint(b, selected["path"])["policy"], restore_rng=False)
        if policy.policy_hash != selected["policy_hash"]:
            raise ValueError("policy hash mismatch")
    else:
        policy = Baseline()
    rows = [r for r in m["entries"] if r["split"] == "test" and
            ((r["surface"] == "clean") == (args.condition in ("E0", "E3")))]
    run_id = c["run_prefix"] + "-" + args.condition
    before = policy.policy_hash
    results = evaluate_rows(b, c, m, rows, policy, workers, run_id, args.condition)
    if policy.policy_hash != before:
        raise RuntimeError("evaluation changed the policy")
    b.json(f"{c['runs_dir']}/{run_id}/environment.json", workers.environment)
    print(f"{args.condition}: recorded {len(results)} real episodes, including failures")
    if any(r["status"] != "complete" for r in results):
        raise RuntimeError("evaluation contains failed episodes; retained in reporting denominator")


if __name__ == "__main__":
    entry(main)
