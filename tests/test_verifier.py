"""
Unit Tests for Independent Verifier Module (agent/verifier.py).
Mocks requests.get to test verification against Finance API and Invoice Portal APIs.
"""

import unittest
from unittest.mock import patch, MagicMock
from agent.verifier import verify_finance_record


class TestVerifier(unittest.TestCase):

    def _create_mock_response(self, json_data, status_code=200):
        mock_resp = MagicMock()
        mock_resp.status_code = status_code
        mock_resp.json.return_value = json_data
        return mock_resp

    @patch("requests.get")
    def test_all_pass(self, mock_get):
        """Test case 1: All checks pass successfully."""
        # Setup mock responses for the 3 HTTP requests made by verifier:
        # 1. Finance record: http://localhost:8002/api/records/INV-2026-003
        fin_rec = {
            "record_id": "REC-1001",
            "invoice_number": "INV-2026-003",
            "vendor": "Acme Technologies",
            "amount": 62400.0,
            "due_date": "2026-10-30"
        }
        # 2. Source invoice: http://localhost:8001/api/invoices/INV-2026-003
        src_inv = {
            "invoice_number": "INV-2026-003",
            "vendor": "Acme Technologies",
            "issue_date": "2026-09-30",
            "amount": 62400.0,
            "due_date": "2026-10-30",
            "status": "Unpaid"
        }
        # 3. Vendor invoices list: http://localhost:8001/api/invoices?vendor=Acme Technologies
        vendor_invs = [
            {"invoice_number": "INV-2026-001", "vendor": "Acme Technologies", "issue_date": "2026-08-15"},
            {"invoice_number": "INV-2026-003", "vendor": "Acme Technologies", "issue_date": "2026-09-30"}
        ]

        mock_get.side_effect = [
            self._create_mock_response(fin_rec),
            self._create_mock_response(src_inv),
            self._create_mock_response(vendor_invs)
        ]

        facts = {
            "invoice_number": "INV-2026-003",
            "vendor": "Acme Technologies",
            "amount": "62400",
            "due_date": "2026-10-30"
        }

        result = verify_finance_record(facts, check_latest=True)

        self.assertTrue(result["passed"])
        self.assertEqual(result["record_id"], "REC-1001")
        self.assertTrue(all(c["ok"] for c in result["checks"]))

    @patch("requests.get")
    def test_mismatched_amount(self, mock_get):
        """Test case 2: Mismatched amount recorded in finance DB causes verification failure."""
        fin_rec = {
            "record_id": "REC-1002",
            "invoice_number": "INV-2026-003",
            "vendor": "Acme Technologies",
            "amount": 45200.0,  # Mismatched amount in DB (expected 62400.0)
            "due_date": "2026-10-30"
        }
        src_inv = {
            "invoice_number": "INV-2026-003",
            "vendor": "Acme Technologies",
            "issue_date": "2026-09-30",
            "amount": 62400.0,
            "due_date": "2026-10-30",
            "status": "Unpaid"
        }
        vendor_invs = [
            {"invoice_number": "INV-2026-003", "vendor": "Acme Technologies", "issue_date": "2026-09-30"}
        ]

        mock_get.side_effect = [
            self._create_mock_response(fin_rec),
            self._create_mock_response(src_inv),
            self._create_mock_response(vendor_invs)
        ]

        facts = {
            "invoice_number": "INV-2026-003",
            "vendor": "Acme Technologies",
            "amount": "62400",
            "due_date": "2026-10-30"
        }

        result = verify_finance_record(facts, check_latest=True)

        self.assertFalse(result["passed"])
        # Amount check and source_amount check should fail
        failed_names = [c["name"] for c in result["checks"] if not c["ok"]]
        self.assertIn("amount", failed_names)
        self.assertIn("source_amount", failed_names)

    @patch("requests.get")
    def test_recorded_invoice_not_latest(self, mock_get):
        """Test case 3: Recorded invoice is not the latest invoice by issue_date."""
        fin_rec = {
            "record_id": "REC-1003",
            "invoice_number": "INV-2026-001",  # Older invoice recorded
            "vendor": "Acme Technologies",
            "amount": 45200.0,
            "due_date": "2026-09-15"
        }
        src_inv = {
            "invoice_number": "INV-2026-001",
            "vendor": "Acme Technologies",
            "issue_date": "2026-08-15",
            "amount": 45200.0,
            "due_date": "2026-09-15",
            "status": "Paid"
        }
        # Portal has INV-2026-003 as a newer invoice (2026-09-30) than INV-2026-001 (2026-08-15)
        vendor_invs = [
            {"invoice_number": "INV-2026-001", "vendor": "Acme Technologies", "issue_date": "2026-08-15"},
            {"invoice_number": "INV-2026-003", "vendor": "Acme Technologies", "issue_date": "2026-09-30"}
        ]

        mock_get.side_effect = [
            self._create_mock_response(fin_rec),
            self._create_mock_response(src_inv),
            self._create_mock_response(vendor_invs)
        ]

        facts = {
            "invoice_number": "INV-2026-001",
            "vendor": "Acme Technologies",
            "amount": "45200",
            "due_date": "2026-09-15"
        }

        result = verify_finance_record(facts, check_latest=True)

        self.assertFalse(result["passed"])
        failed_names = [c["name"] for c in result["checks"] if not c["ok"]]
        self.assertIn("source_latest_invoice", failed_names)
        latest_check = next(c for c in result["checks"] if c["name"] == "source_latest_invoice")
        self.assertEqual(latest_check["expected"], "INV-2026-003")
        self.assertEqual(latest_check["actual"], "INV-2026-001")


if __name__ == "__main__":
    unittest.main()
