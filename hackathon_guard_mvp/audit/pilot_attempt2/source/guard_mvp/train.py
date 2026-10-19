"""Live current-policy rollout collection and bounded MAPPO training; PBS only."""
import random
import time
from .io import cli, entry, file_hash
from .validate_data import validate
from .policies import Baseline
from .runtime import (require_pilot, identity, episode, evaluate_rows, save_checkpoint, load_checkpoint)
from .workers import FrozenWorkers, require_allocation


def choose_case(rows, index, seed):
    # Balanced 12-episode schedule: six clean, three document, three handoff,
    # equally divided over objectives. Sampling repeats histories explicitly.
    workflow = ("receipt", "supplier", "collection")[index % 3]
    surface = ("clean", "document", "clean", "handoff")[(index // 3) % 4]
    pool = [r for r in rows if r["workflow"] == workflow and r["surface"] == surface]
    return random.Random(seed + index).choice(pool)


def utility(rows):
    return dict(clean=sum(r["safe_task_success"] for r in rows if r["attack_surface"] == "clean"),
                attacked=sum(r["safe_task_success"] for r in rows if r["attack_surface"] != "clean"),
                cost=sum(r["input_tokens"] + r["output_tokens"] for r in rows),
                failures=sum(r["status"] != "complete" for r in rows))


def select_checkpoint(b, c, m, policy, workers, progress, path, baseline):
    rows = [r for r in m["entries"] if r["split"] == "validation"]
    results = evaluate_rows(b, c, m, rows, policy, workers, f"validation-{progress}", f"VALIDATION-{progress}")
    score = utility(results)
    eligible = score["failures"] == 0 and score["clean"] >= baseline["clean"] - 1
    selected = b.read(c["checkpoint"]) if b.path(c["checkpoint"]).exists() else None
    if selected and selected["identity"] != identity(b, c, m):
        raise ValueError("existing selection belongs to another experiment freeze")
    rank = [score["attacked"], -score["cost"]]
    if eligible and (selected is None or rank > selected["rank"]):
        b.json(c["checkpoint"], dict(path=path, sha256=file_hash(b.path(path)), policy_hash=policy.policy_hash,
                                    identity=identity(b, c, m), progress=progress, rank=rank, validation=score,
                                    heuristic_validation=baseline,
                                    improves_heuristic=(score["attacked"] > baseline["attacked"] or
                                                       (score["attacked"] == baseline["attacked"] and score["cost"] < baseline["cost"])),
                                    product_recommendation="retain fixed baseline unless validation utility/cost improves"))
    b.json(f"runs/training/validation-{progress}.json", dict(eligible=eligible, score=score, heuristic=baseline))


def main():
    _, b, c = cli("Bounded live MAPPO collection and training; no LLM fine-tuning")
    m = validate(b, c)
    require_pilot(b, c, m)
    torch = require_allocation(c)
    from .learner import MAPPO
    torch.set_num_threads(2)
    torch.manual_seed(c["seed"])
    random.seed(c["seed"])
    policy = MAPPO(c["training"])
    workers = FrozenWorkers(b, c)
    expected_identity = identity(b, c, m)
    latest = "runs/training/latest.pt"
    progress, rollout, elapsed = 0, [], 0.0
    if b.path(latest).exists():
        saved = load_checkpoint(b, latest)
        if saved["identity"] != expected_identity:
            raise ValueError("training resume identity mismatch")
        policy.load_state_dict(saved["policy"])
        progress, rollout, elapsed = saved["progress"], saved["rollout"], saved["elapsed_seconds"]
        workers.total_tokens = saved["tokens"]
        workers.accounted_records = set(saved["accounted_records"])
    start = time.monotonic()
    workers.started -= elapsed
    baseline_rows = evaluate_rows(b, c, m, [r for r in m["entries"] if r["split"] == "validation"],
                                  Baseline(), workers, "validation-baseline", "VALIDATION-BASELINE")
    baseline = utility(baseline_rows)
    if baseline["failures"]:
        raise RuntimeError("validation baseline infrastructure failure")
    b.json("runs/training/environment.json", workers.environment)
    rows = [r for r in m["entries"] if r["split"] == "train"]

    def save():
        save_checkpoint(b, latest, dict(identity=expected_identity, policy=policy.state_dict(), progress=progress,
                                       rollout=rollout, tokens=workers.total_tokens,
                                       accounted_records=sorted(workers.accounted_records),
                                       elapsed_seconds=time.monotonic() - workers.started))

    def validate_pending():
        if progress and not rollout and (progress % c["training"]["validate_every"] == 0 or progress == c["training"]["episodes"]):
            marker = f"runs/training/validation-{progress}.json"
            if not b.path(marker).exists():
                path = f"runs/training/checkpoints/episode-{progress}.pt"
                b.write(path, b.path(latest).read_bytes())
                select_checkpoint(b, c, m, policy, workers, progress, path, baseline)
                save()

    # Recover interruption after an update/checkpoint but before validation.
    validate_pending()

    while progress < c["training"]["episodes"] or rollout:
        if workers.total_tokens >= c["limits"]["tokens"] or time.monotonic() - workers.started >= c["limits"]["wall_seconds"]:
            save()
            raise RuntimeError("training campaign budget exhausted; checkpoint retained")
        if len(rollout) >= c["training"]["batch_episodes"] or progress == c["training"]["episodes"]:
            losses = policy.update(rollout)
            rollout = []
            save()
            b.json(f"runs/training/metrics/update-{progress}.json", dict(losses=losses, episodes=progress))
            validate_pending()
            continue
        # A completed episode record is the transaction journal. If interrupted
        # between record and checkpoint, resume its stored RNG/transition once.
        row = choose_case(rows, progress, c["seed"])
        target = f"runs/training/episodes/{progress:05d}.json"
        if b.path(target).exists():
            record = b.read(target)
            if record["result"]["case_id"] != row["case_id"] or record["result"]["policy_hash"] != policy.policy_hash:
                raise ValueError("training journal mismatch")
            torch.set_rng_state(torch.tensor(record["post_rng"], dtype=torch.uint8))
            workers.total_tokens = max(workers.total_tokens, record["total_tokens"])
            workers.started -= record["result"]["elapsed_seconds"]
        else:
            record = episode(b, c, row, policy, workers, "TRAIN", "training", deterministic=False)
            record["result"]["trace_reference"] = f"episodes/{progress:05d}.json#trace"
            record["post_rng"] = torch.get_rng_state().tolist()
            record["total_tokens"] = workers.total_tokens
            b.json(target, record)
        rollout.append({"steps": record["steps"], "reward": record["reward"]})
        progress += 1
        save()
        if record["result"]["status"] != "complete":
            raise RuntimeError("training episode failed; stopped at persisted boundary: " + str(record["result"]["error_type"]))
    if not b.path(c["checkpoint"]).exists():
        raise RuntimeError("no checkpoint met validation clean-utility floor; retain baseline")
    b.json("runs/training/completion.json", dict(identity=expected_identity, episodes=progress, selected=b.read(c["checkpoint"])))
    print(f"Completed {progress} episodes; checkpoint selected using validation only")


if __name__ == "__main__":
    entry(main)
