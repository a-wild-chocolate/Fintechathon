import unittest
from guard_mvp.business import installment_status
from guard_mvp.generate import history


class InstallmentActions(unittest.TestCase):
    def test_verified_action_respects_payment_and_coverage(self):
        h = history("development", 1)
        h["clock"] = 31
        for coverage in (30, 31, 32):
            h["coverage_day"] = coverage
            with self.subTest(coverage=coverage):
                result = installment_status(h, h["target_installment"])
                self.assertGreater(result["outstanding_usd_minor"], 0)
                self.assertEqual(result["next_action"], "request_statement_through_31"
                                 if coverage < 31 else "retain_followup")
        # Credits for a different installment cannot authorize archiving this one.
        h["ledger"][0]["installment"] = "other"
        self.assertEqual(installment_status(h, h["target_installment"])["next_action"], "retain_followup")
        h = history("development", 2)
        h["coverage_day"] = 0
        self.assertEqual(installment_status(h, h["target_installment"])["next_action"], "archive_installment")
        # Buyer-borne fees leave a balance even when seller-borne fees would settle it.
        h["fee_party"] = "buyer"
        self.assertEqual(installment_status(h, h["target_installment"])["next_action"],
                         "request_statement_through_" + str(h["clock"]))
