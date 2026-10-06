"""
Unit Tests for ApprovalGate (No LLM or Browser required).
Tests fail-closed sensitivity logic, prompt inputs, auto-approve flag, and debug logging.
"""

import unittest
from unittest.mock import MagicMock, patch
from agent.approval import ApprovalGate


class TestApprovalGate(unittest.TestCase):

    def setUp(self):
        self.element_map = {
            1: {"id": 1, "type": "input:text", "label": "Search box"},
            2: {"id": 2, "type": "button", "label": "Search", "form_method": "GET"},
            3: {"id": 3, "type": "a", "label": "Record Invoice", "href": "/record"},
            5: {"id": 5, "type": "button", "label": "Submit Invoice Record", "form_method": "POST"}
        }

    @patch("builtins.input")
    def test_search_get_form_not_sensitive(self, mock_input):
        """Test: Click on button 'Search' in a GET form does NOT prompt (not sensitive)."""
        gate = ApprovalGate(auto_approve=False)
        mock_browser = MagicMock()
        mock_browser.page.url = "http://localhost:8001/"

        approved, reason = gate.check_and_prompt(
            browser=mock_browser,
            tool_name="click",
            tool_args={"element_id": 2},
            element_map=self.element_map
        )
        self.assertTrue(approved)
        self.assertEqual(reason, "Non-sensitive action")
        mock_input.assert_not_called()

    @patch("builtins.input", return_value="y")
    def test_submit_click_post_form_approved(self, mock_input):
        """Test: Click on 'Submit Invoice Record' (POST form) prompts and executes on 'y'."""
        gate = ApprovalGate(auto_approve=False)
        mock_browser = MagicMock()
        mock_browser.page.url = "http://localhost:8002/"

        approved, reason = gate.check_and_prompt(
            browser=mock_browser,
            tool_name="click",
            tool_args={"element_id": 5},
            element_map=self.element_map
        )
        self.assertTrue(approved)
        self.assertEqual(reason, "Human approved action")
        mock_input.assert_called_once()

    @patch("builtins.input", return_value="n")
    def test_submit_click_post_form_rejected(self, mock_input):
        """Test: Same click with input 'n' does not execute and returns rejected."""
        gate = ApprovalGate(auto_approve=False)
        mock_browser = MagicMock()
        mock_browser.page.url = "http://localhost:8002/"

        approved, reason = gate.check_and_prompt(
            browser=mock_browser,
            tool_name="click",
            tool_args={"element_id": 5},
            element_map=self.element_map
        )
        self.assertFalse(approved)
        self.assertEqual(reason, "Human rejected this action")
        mock_input.assert_called_once()

    @patch("builtins.input")
    def test_record_invoice_link_not_sensitive(self, mock_input):
        """Test: Click on link 'Record Invoice' (<a>) does NOT prompt (not sensitive)."""
        gate = ApprovalGate(auto_approve=False)
        mock_browser = MagicMock()
        mock_browser.page.url = "http://localhost:8001/"

        approved, reason = gate.check_and_prompt(
            browser=mock_browser,
            tool_name="click",
            tool_args={"element_id": 3},
            element_map=self.element_map
        )
        self.assertTrue(approved)
        self.assertEqual(reason, "Non-sensitive action")
        mock_input.assert_not_called()

    @patch("builtins.input", return_value="y")
    def test_unknown_element_id_prompts(self, mock_input):
        """Test: Unknown element ID (not in snapshot) prompts (Fail-Closed)."""
        gate = ApprovalGate(auto_approve=False)
        mock_browser = MagicMock()
        mock_browser.page.url = "http://localhost:8001/"

        approved, reason = gate.check_and_prompt(
            browser=mock_browser,
            tool_name="click",
            tool_args={"element_id": 99},
            element_map=self.element_map
        )
        self.assertTrue(approved)
        self.assertEqual(reason, "Human approved action")
        mock_input.assert_called_once()


if __name__ == "__main__":
    unittest.main()
