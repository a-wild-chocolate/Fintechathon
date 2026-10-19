"""Actor contract constructed exclusively from visible episode state."""
ROUTES = ("bank", "agreement", "installment", "cash")
EVIDENCE_ACTIONS = ("none", "bank", "agreement", "installment", "cash", "reuse", "clarify")
RECOVERY_ACTIONS = ("continue", "recompute", "rerun", "preserve", "finalize")
FEATURES = 16


def observe(visible, verified, cycle, rerun, finalized, answer):
    wf = visible["workflow"]
    common = [float(wf == k) for k in ("receipt", "supplier", "collection")]
    common += [cycle / 3, float(rerun), float(finalized), visible["clock"] / 55,
               visible["supplierDay"] / 55]
    flags = [float(k in verified and verified[k]["version"] == visible["version"]) for k in ROUTES]
    # Presence/version are inspectable; these are not truth-support labels.
    evidence = common + flags + [len(visible["sources"]) / 4, float(visible["permissions"]["verify"]),
                                 float(bool(answer)), float(any(v is None or v == "" for v in answer.values()))]
    cash = verified.get("cash", {}).get("data", {})
    installment = verified.get("installment", {}).get("data", {})
    recovery = common + flags + [cash.get("available_cny_minor", 0) / 16000000,
                                 cash.get("supplier_gap_minor", 0) / 16000000,
                                 installment.get("outstanding_usd_minor", 0) / 1200000,
                                 float(installment.get("absence_conclusive") is False)]
    return {"evidence": evidence, "recovery": recovery}


def masks(visible, verified, rerun):
    permitted = visible["permissions"]["verify"]
    return {"evidence": [True] + [permitted] * 4 + [bool(verified), True],
            "recovery": [True, permitted, not rerun, True, True]}
