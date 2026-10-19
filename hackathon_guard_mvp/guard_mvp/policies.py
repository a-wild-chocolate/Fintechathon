"""Fixed verification heuristic on exactly the same contract as learned actors."""
from .io import digest


class Baseline:
    name = "verify-unsupported-claims-v1"
    policy_hash = digest({"policy": name, "evidence": "bank/agreement/installment", "recovery": [1, 2, 4]})

    def choose(self, role, views, mask, deterministic=True):
        v = views[role]
        cycle = round(v[3] * 3)
        if role == "evidence":
            preferred = (2 if v[1] else 1) if cycle == 0 else (3 if cycle == 1 else 5)
        else:
            preferred = [1, 2, 4][min(cycle, 2)]
        action = preferred if mask[preferred] else next(i for i, ok in enumerate(mask) if ok)
        return action, None
