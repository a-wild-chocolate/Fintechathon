from collections import Counter, defaultdict
from .io import cli, digest, entry


def validate(b, c):
    m = b.read(f"{c['data_dir']}/manifests/dataset.json")
    if digest({k: v for k, v in m.items() if k != "manifest_hash"}) != m["manifest_hash"]:
        raise ValueError("manifest checksum mismatch")
    private = b.read(f"{c['private_dir']}/answers.json")
    if digest(private) != m["private_hash"]:
        raise ValueError("private manifest checksum mismatch")
    attacks = b.read(f"{c['private_dir']}/attack_manifest.json")
    if attacks != [r for r in m["entries"] if r["surface"] != "clean"]:
        raise ValueError("attack assignment manifest mismatch")
    grouped = defaultdict(list)
    tenants = defaultdict(set)
    seen = set()
    counts = Counter()
    for r in m["entries"]:
        if r["case_id"] in seen:
            raise ValueError("duplicate case")
        seen.add(r["case_id"])
        grouped[r["base_case_id"]].append(r)
        counts[r["split"]] += 1
        for k, path in r["paths"].items():
            if digest(b.read(path)) != r["hashes"][k]:
                raise ValueError("data checksum mismatch: " + path)
        visible = b.read(r["paths"]["visible"])
        tenants[visible["tenant"]].add(r["split"])
        forbidden = {"surface", "attack_exposed", "attacker_goal_success", "expected", "truth", "case_id", "base_case_id", "split"}
        if forbidden.intersection(visible):
            raise ValueError("private metadata in visible data")
        if digest(private[r["case_id"]]["expected"]) != r["truth_hash"]:
            raise ValueError("truth mismatch")
        intervention = private[r["case_id"]]["intervention"]
        if intervention["surface"] != r["surface"]:
            raise ValueError("intervention assignment mismatch")
        if r["surface"] == "handoff" and digest(intervention["payload"]) != r["payload_hash"]:
            raise ValueError("handoff payload checksum mismatch")
    if counts != Counter(development=36, train=600, validation=120, test=180):
        raise ValueError("partition size mismatch")
    if any(len(s) != 1 for s in tenants.values()):
        raise ValueError("tenant leakage")
    for rs in grouped.values():
        if (len(rs) != 3 or {r["surface"] for r in rs} != {"clean", "document", "handoff"}
                or len({r["split"] for r in rs}) != 1 or len({r["truth_hash"] for r in rs}) != 1
                or len({r["hashes"]["operational"] for r in rs}) != 1):
            raise ValueError("paired grouping/truth failure")
        docs = {r["surface"]: b.read(r["paths"]["visible"]) for r in rs}
        if docs["clean"] != docs["handoff"]:
            raise ValueError("handoff must preserve visible sources")
        clean, attacked = docs["clean"], docs["document"]
        if {k: v for k, v in clean.items() if k != "sources"} != {k: v for k, v in attacked.items() if k != "sources"}:
            raise ValueError("document intervention changed protected state")
        if not attacked["sources"][0]["text"].startswith(clean["sources"][0]["text"] + "\n"):
            raise ValueError("document intervention missing")
        original = clean["sources"][0]["text"]
        payload = attacked["sources"][0]["text"][len(original) + 1:]
        if any(r["original_hash"] != digest(original) for r in rs):
            raise ValueError("original source hash mismatch")
        if any(r["payload_hash"] != digest(payload) for r in rs if r["surface"] != "clean"):
            raise ValueError("payload hash mismatch")
    grid = Counter((r["workflow"], r["surface"]) for r in m["entries"] if r["split"] == "test")
    if len(grid) != 9 or set(grid.values()) != {20}:
        raise ValueError("unbalanced final test grid")
    return m


def main():
    _, b, c = cli("Validate all hashes, paired histories and partitions")
    m = validate(b, c)
    print(f"PASS: {len(m['entries'])} presentations; grouped 200/40/60 and separate 12-case development set")


if __name__ == "__main__":
    entry(main)
