"""Read-only bridge to actual pure JS functions. No browser, storage or API imports."""
import json
import subprocess
from pathlib import Path


class ApplicationAdapter:
    def __init__(self, b, node):
        self.b = b
        self.node = node
        if not Path(node).is_file():
            raise FileNotFoundError("configured Node executable absent")

    def call(self, function, payload):
        p = subprocess.run([self.node, str(self.b.path("scripts/application_bridge.mjs"))],
                           input=json.dumps({"function": function, "payload": payload}), text=True,
                           cwd=self.b.root, capture_output=True, timeout=20, check=True)
        return json.loads(p.stdout)

    def forecast(self, visible):
        # Existing application's projection includes promised receipts. It is explicitly
        # labelled a forecast, never used as an authoritative bank balance.
        flow = {"version": visible["version"], "opening": visible["opening_minor"] / 100,
                "supplierDay": visible["supplierDay"], "receiptDay": visible["receiptDay"], "jobs": []}
        return {"forecast": self.call("enrich", flow),
                "reminders": self.call("followupView", {"flow": flow, "day": visible["clock"]}),
                "label": "application scenario forecast; not posted cash"}
