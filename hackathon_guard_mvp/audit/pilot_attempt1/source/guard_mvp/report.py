"""Reports only manifest-complete real evaluation records. No illustrative values."""
import csv
import html
import io
from collections import defaultdict
from .io import cli, entry, file_hash
from .validate_data import validate
from .runtime import identity

METRICS = ("task_success", "safe_task_success", "attacker_goal_success", "harmful_recommendation", "committed_violations", "escalation", "unnecessary_escalation")


def summarize(rows):
    n = len(rows)
    out = {k: {"count": sum(bool(r[k]) for r in rows), "denominator": n,
               "rate": sum(bool(r[k]) for r in rows) / n if n else None} for k in METRICS}
    exposed = [r for r in rows if r["attack_exposed"]]
    out["exposure"] = {"count": len(exposed), "denominator": sum(r["attack_surface"] != "clean" for r in rows)}
    out["asr_exposed"] = {"count": sum(r["attacker_goal_success"] for r in exposed), "denominator": len(exposed),
                          "rate": sum(r["attacker_goal_success"] for r in exposed) / len(exposed) if exposed else None}
    out["failed_episodes"] = sum(r["status"] != "complete" for r in rows)
    out["blocked_unsafe_proposals"] = sum(r["blocked_unsafe_proposals"] for r in rows)
    out["costs"] = {k: sum(r[k] for r in rows) for k in ("llm_calls", "input_tokens", "output_tokens", "verification_calls", "elapsed_seconds")}
    return out


def csv_text(rows, fields):
    s = io.StringIO()
    w = csv.DictWriter(s, fields, extrasaction="ignore")
    w.writeheader()
    w.writerows(rows)
    return s.getvalue()


def main():
    _, b, c = cli("Export actual final metrics, plots, costs and trace replay")
    m = validate(b, c)
    missing = [k for k in ("E0", "E1", "E2", "E3") if not b.path(f"{c['runs_dir']}/{c['run_prefix']}-{k}/metrics/results.json").exists()]
    if missing:
        message = "MISSING RESULTS: " + ", ".join(missing) + ". No live final campaign has been reported; no performance plots generated."
        b.write(f"{c['reports_dir']}/missing-results.txt", message + "\n")
        print(message)
        raise SystemExit(2)
    selected = b.read(c["checkpoint"])
    all_rows, summaries = [], {}
    for condition in ("E0", "E1", "E2", "E3"):
        run_id = c["run_prefix"] + "-" + condition
        prefix = f"{c['runs_dir']}/{run_id}"
        metadata = b.read(prefix + "/config.json")
        if any(metadata[k] != v for k, v in identity(b, c, m).items()):
            raise ValueError("run freeze mismatch")
        rows = b.read(prefix + "/metrics/results.json")
        expected = {r["case_id"] for r in m["entries"] if r["split"] == "test" and
                    ((r["surface"] == "clean") == (condition in ("E0", "E3")))}
        if len(rows) != len(expected) or {r["case_id"] for r in rows} != expected:
            raise ValueError("incomplete or duplicated final manifest coverage")
        for r in rows:
            if r["condition"] != condition or r["model_revision"] != c["model"]["revision"] or r["backend"] != c["backend"]:
                raise ValueError("mixed evaluation condition/backend/model")
            episode = b.read(prefix + f"/episodes/{r['case_id']}.json")
            if episode["result"] != r or not episode["trace"]:
                raise ValueError("missing actual episode trace")
            if r["policy_hash"] != metadata["policy_hash"]:
                raise ValueError("mixed policy hashes")
            if condition in ("E2", "E3") and r["policy_hash"] != selected["policy_hash"]:
                raise ValueError("not the selected validation checkpoint")
        all_rows.extend(rows)
        summaries[condition] = summarize(rows)
    breakdown = defaultdict(list)
    for r in all_rows:
        if r["attack_surface"] != "clean":
            breakdown[(r["condition"], r["workflow"], r["attack_surface"])].append(r)
    out = c["reports_dir"]
    b.json(out + "/metrics.json", {"seed": c["seed"], "conditions": summaries,
                                  "attack_breakdown": {"/".join(k): summarize(v) for k, v in breakdown.items()}})
    b.write(out + "/results.csv", csv_text(all_rows, list(all_rows[0])))
    b.write(out + "/costs.csv", csv_text(all_rows, ["condition", "case_id", "llm_calls", "input_tokens", "output_tokens", "verification_calls", "elapsed_seconds"]))
    table = [dict(condition=k, **v["safe_task_success"]) for k, v in summaries.items()]
    b.write(out + "/clean-retention.csv", csv_text([r for r in table if r["condition"] in ("E0", "E3")], ["condition", "count", "denominator", "rate"]))
    b.write(out + "/attack-breakdown.csv", csv_text([dict(condition=k[0], workflow=k[1], surface=k[2], **summarize(v)["safe_task_success"]) for k, v in breakdown.items()],
                                                  ["condition", "workflow", "surface", "count", "denominator", "rate"]))
    # Standard plotting library, imported only after real data validation.
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    for name, arms in (("three-condition", ("E0", "E1", "E2")), ("clean-retention", ("E0", "E3"))):
        fig, ax = plt.subplots(figsize=(6, 4))
        ax.bar([f"{a} ({'clean' if a in ('E0','E3') else 'attacked'})" for a in arms],
               [summaries[a]["safe_task_success"]["rate"] for a in arms])
        ax.set(ylim=(0, 1), ylabel="Safe task completion", title="Synthetic MVP sandbox — actual final evaluation")
        fig.tight_layout()
        fig.savefig(b.path(out + "/" + name + ".png"))
        plt.close(fig)
    content = "<!doctype html><meta charset='utf-8'><title>CashWeave Guard results</title><h1>Synthetic sandbox results</h1>"
    content += "<p>Single seed; synthetic histories. Failures remain in denominators. No real-world robustness guarantee.</p>"
    for r in all_rows:
        prefix = f"{c['runs_dir']}/{r['run_id']}/episodes/{r['case_id']}.json"
        trace = b.read(prefix)
        content += "<details><summary>" + html.escape(f"{r['condition']} {r['case_id']} {r['status']} safe={r['safe_task_success']}") + "</summary><pre>"
        import json
        content += html.escape(json.dumps(trace, indent=2)) + "</pre></details>"
    b.write(out + "/replay.html", content)
    missing_notice = b.path(out + "/missing-results.txt")
    if missing_notice.exists():
        missing_notice.unlink()
    b.json(out + "/artifact_hashes.json", {p.name: file_hash(p) for p in b.path(out).iterdir() if p.is_file() and p.name != "artifact_hashes.json"})
    print(f"Exported {len(all_rows)} real episode outcomes to {out}")


if __name__ == "__main__":
    entry(main)
