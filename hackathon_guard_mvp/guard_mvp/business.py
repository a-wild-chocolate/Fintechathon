"""Prototype financial services. No evaluator imports; authorized operational records only."""
import copy
from decimal import Decimal, ROUND_HALF_UP
from .io import digest


def convert(minor, rate):
    return int((Decimal(minor) * Decimal(rate)).quantize(Decimal("1"), rounding=ROUND_HALF_UP))


def posted_credits(records, clock):
    unique = {}
    for row in records:
        if row["id"] in unique and unique[row["id"]] != row:
            raise ValueError("conflicting duplicate credit")
        unique[row["id"]] = row
    return [r for r in unique.values() if r["posted_day"] <= clock]


def cash_position(h, supplier_day=None):
    day = h["supplierDay"] if supplier_day is None else supplier_day
    credits = posted_credits(h["ledger"], h["clock"])
    def at(t):
        return (h["opening_minor"] + sum(convert(r["net_usd_minor"], r["fx"]) for r in credits
                if h["opening_day"] < r["available_day"] <= t)
                + sum(e["minor"] for e in h["company_events"] if h["opening_day"] < e["day"] <= t))
    return {"available_cny_minor": at(h["clock"]), "supplier_gap_minor": max(0, h["supplier_minor"] - at(day)),
            "scope": "company", "fx_basis": "hypothetical scenario rates; CNY available only on FX value date"}


def installment_status(h, installment):
    credits = [r for r in posted_credits(h["ledger"], h["clock"]) if r["installment"] == installment]
    net = sum(r["net_usd_minor"] for r in credits)
    fees = sum(r["fee_usd_minor"] for r in credits)
    settled = net + (fees if h["fee_party"] == "seller" else 0)
    remaining = max(0, h["invoice_usd_minor"] - settled)
    return {"installment": installment, "net_usd_minor": net, "fees_usd_minor": fees,
            "outstanding_usd_minor": remaining, "fee_party": h["fee_party"],
            "receipt_status": "settled" if remaining == 0 else ("partial" if net else "unconfirmed"),
            "coverage_day": h["coverage_day"], "absence_conclusive": h["coverage_day"] >= h["clock"],
            "followup_state": "closed" if remaining == 0 else "open"}


class Gateway:
    """Capability-limited gateway. Workers receive JSON results, never this object."""
    def __init__(self, operational):
        self.__records = copy.deepcopy(operational)
        self.state = {"version": operational["version"], "supplierDay": operational["supplierDay"],
                      "followup_state": operational["followup_state"], "supplier_updated": False}
        self.blocked = 0
        self.verifications = 0
        self.events = {}
        self.__approvals = {}
        self.__original = digest(operational)

    def verify(self, route):
        if not self.__records["permissions"]["verify"]:
            raise PermissionError("verification is not authorized")
        self.verifications += 1
        h = self.__records
        if route == "bank":
            out = {"ledger": copy.deepcopy(posted_credits(h["ledger"], h["clock"])), "coverage_day": h["coverage_day"],
                   "opening_minor": h["opening_minor"], "opening_day": h["opening_day"]}
        elif route == "agreement":
            out = copy.deepcopy(h["agreement"])
            if out["accepted"] and h["permissions"]["update_supplier"]:
                params = dict(day=out["day"], order_id=h["order_id"])
                binding = dict(action="supplier", params=params, version=self.state["version"], tenant=h["tenant"])
                token = digest(binding)
                self.__approvals[token] = binding
                out["approval_token"] = token
        elif route == "installment":
            out = installment_status(h, h["target_installment"])
        elif route == "cash":
            agreement = h["agreement"]
            day = agreement["day"] if agreement["accepted"] and h["permissions"]["update_supplier"] else self.state["supplierDay"]
            out = cash_position(h, day)
        else:
            raise ValueError("unknown verification route")
        return {"source": "authorized_" + route, "version": self.state["version"], "data": out}

    def propose(self, action, params, version, event_id, approval=None):
        binding = digest([action, params, version, approval])
        if event_id in self.events:
            if self.events[event_id][0] != binding:
                self.blocked += 1
                return {"accepted": False, "reason": "event_conflict"}
            return copy.deepcopy(self.events[event_id][1])
        h = self.__records
        reason = None
        if version != self.state["version"]:
            reason = "stale_version"
        elif action == "supplier":
            expected = dict(action=action, params=params, version=version, tenant=h["tenant"])
            if not h["permissions"]["update_supplier"] or self.__approvals.get(approval) != expected:
                reason = "approval_not_bound_to_parameters"
        elif action == "close":
            if (not h["permissions"]["close_followup"] or params != {"installment": h["target_installment"]}
                    or installment_status(h, h["target_installment"])["outstanding_usd_minor"] != 0):
                reason = "installment_unresolved_or_unauthorized"
        else:
            reason = "action_not_authorized"
        if reason:
            self.blocked += 1
            result = {"accepted": False, "reason": reason}
        else:
            if action == "supplier":
                self.state.update(supplierDay=params["day"], supplier_updated=True)
            else:
                self.state["followup_state"] = "closed"
            self.state["version"] += 1
            result = {"accepted": True, "version": self.state["version"]}
        self.events[event_id] = (binding, result)
        assert digest(self.__records) == self.__original
        return copy.deepcopy(result)
