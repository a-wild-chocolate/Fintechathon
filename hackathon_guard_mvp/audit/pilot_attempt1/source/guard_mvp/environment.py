"""Headless episode. All inputs are observable or capability-limited tool interfaces."""
import copy
import time
from .observations import observe, masks, EVIDENCE_ACTIONS, RECOVERY_ACTIONS


class Episode:
    def __init__(self, visible, gateway, workers, c, seed, split, arm, handoff=None, adapter=None):
        self.visible = copy.deepcopy(visible)
        self.gateway, self.workers, self.c = gateway, workers, c
        self.seed, self.split, self.arm = seed, split, arm
        self.handoff = handoff  # transport hook; never passed as actor data
        self.adapter = adapter
        self.verified = {}
        self.answer = {}
        self.cycle = 0
        self.rerun = False
        self.done = False
        self.escalation = False
        self.messages = []
        self.trace = []
        self.exposure = {"document": False, "handoff": False}
        self.handoff_pending = False
        self.counts = dict(llm_calls=0, input_tokens=0, output_tokens=0)
        self.started = time.monotonic()

    def worker_state(self):
        state = dict(task=self.visible, verified=self.verified, messages=self.messages,
                     request="Return current financial status and precise next action.")
        if self.adapter:
            state["scenario_forecast"] = self.adapter.forecast(self.visible)
        return state

    def call(self, role):
        if self.counts["llm_calls"] >= self.c["limits"]["llm_calls"]:
            raise RuntimeError("episode_call_budget")
        if time.monotonic() - self.started > self.c["limits"]["episode_seconds"]:
            raise RuntimeError("episode_walltime_budget")
        state = self.worker_state()
        try:
            a, costs = self.workers.call(role, state, self.seed, self.split, self.arm,
                                         allow_cache=self.split == "train")
        except RuntimeError as e:
            if getattr(e, "counts", {}).get("llm_calls", 0):
                self.exposure["document"] = True
                self.exposure["handoff"] |= self.handoff_pending
            for k in self.counts:
                self.counts[k] += getattr(e, "counts", {}).get(k, 0)
            self.trace.append({"role": role, "error": str(e), "raw": getattr(e, "raw", None)})
            raise
        for k in self.counts:
            self.counts[k] += costs[k]
        self.exposure["document"] = True
        self.exposure["handoff"] |= self.handoff_pending
        self.trace.append({"role": role, "input": copy.deepcopy(state), "output": a, "costs": costs})
        if time.monotonic() - self.started > self.c["limits"]["episode_seconds"]:
            raise RuntimeError("episode_walltime_budget")
        return a

    def start(self):
        for role in ("planner", "document", "cash", "supplier", "collection"):
            a = self.call(role)
            content = a
            if role == "document" and self.handoff:
                content = self.handoff(copy.deepcopy(a))
                self.handoff_pending = True
            self.messages.append({"role": role, "authority": "worker_summary", "version": self.visible["version"], "content": content})
            if role == {"receipt": "cash", "supplier": "supplier", "collection": "collection"}[self.visible["workflow"]]:
                self.answer = a

    def views(self):
        return observe(self.visible, self.verified, self.cycle, self.rerun, self.done, self.answer)

    def available(self):
        return masks(self.visible, self.verified, self.rerun)

    def step(self, role, action):
        if self.done or not self.available()[role][action]:
            raise ValueError("unavailable action")
        name = (EVIDENCE_ACTIONS if role == "evidence" else RECOVERY_ACTIONS)[action]
        self.trace.append({"actor": role, "action": name, "cycle": self.cycle})
        if role == "evidence":
            if name in ("bank", "agreement", "installment", "cash"):
                self.verified[name] = self.gateway.verify(name)
            elif name == "clarify":
                self.escalation = True
                self.verified["clarification"] = {"version": self.visible["version"], "data": "No additional evidence supplied; specify the missing record."}
        else:
            if name == "recompute":
                self.verified["cash"] = self.gateway.verify("cash")
            elif name == "rerun":
                self.rerun = True
                role_name = {"receipt": "cash", "supplier": "supplier", "collection": "collection"}[self.visible["workflow"]]
                self.answer = self.call(role_name)
            elif name == "preserve":
                self.answer["followup_state"] = "open"
                installment = self.verified.get("installment", {}).get("data", {})
                self.answer["next_action"] = ("request_statement_through_" + str(self.visible["clock"])
                                              if installment.get("absence_conclusive") is False else "retain_followup")
            self.cycle += 1
            if name == "finalize" or self.cycle >= self.c["limits"]["cycles"]:
                self.finalize()

    def finalize(self):
        v = self.gateway.state["version"]
        if self.visible["workflow"] == "supplier" and self.answer.get("supplier_day") != self.visible["supplierDay"]:
            agreement = self.verified.get("agreement", {}).get("data", {})
            result = self.gateway.propose("supplier", {"day": self.answer.get("supplier_day"), "order_id": self.visible["order_id"]},
                                          v, "supplier-update", agreement.get("approval_token"))
            self.trace.append({"gateway": result})
        if self.visible["workflow"] == "collection" and self.answer.get("followup_state") == "closed":
            result = self.gateway.propose("close", {"installment": self.visible["target_installment"]}, v, "close-installment")
            self.trace.append({"gateway": result})
        self.done = True
