from .io import cli, entry
from .validate_data import validate
from .policies import Baseline
from .runtime import identity, evaluate_rows, check_originals
from .workers import FrozenWorkers


def main():
    _, b, c = cli("Live 12-clean/24-attacked development pilot; PBS only")
    m = validate(b, c)
    check_originals(b)
    hard = b.read("audit/cpu_checks.json")
    from .runtime import source_hash
    if not hard["passed"] or hard["source_hash"] != source_hash(b):
        raise RuntimeError("current hard-control tests must pass before GPU work")
    workers = FrozenWorkers(b, c)
    rows = [r for r in m["entries"] if r["split"] == "development"]
    results = evaluate_rows(b, c, m, rows, Baseline(), workers, "pilot", "PILOT")
    clean = [r for r in results if r["attack_surface"] == "clean"]
    exposed = sum(r["attack_exposed"] for r in results)
    passed = (sum(r["safe_task_success"] for r in clean) / len(clean) >= c["pilot"]["minimum_clean_success"]
              and exposed >= c["pilot"]["minimum_exposed_attacks"] and all(r["status"] == "complete" for r in results))
    gate = dict(passed=passed, identity=identity(b, c, m), clean_safe=sum(r["safe_task_success"] for r in clean),
                clean_denominator=len(clean), exposed_attacks=exposed, attacked_denominator=24,
                learnable_failures=sum(not r["safe_task_success"] for r in results if r["attack_surface"] != "clean"))
    b.json("audit/pilot_gate.json", gate)
    b.json("runs/pilot/environment.json", workers.environment)
    b.json("audit/frozen_experiment.json", dict(gate["identity"], frozen=passed))
    print(gate)
    if not passed:
        raise RuntimeError("pilot gate failed; inspect real traces before any campaign")


if __name__ == "__main__":
    entry(main)
