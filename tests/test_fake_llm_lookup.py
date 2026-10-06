"""
Unit Tests for FakeLLM element lookup and date parsing (tests/test_fake_llm_lookup.py).
Runs without LLM or browser.
"""

import unittest
from agent.fake_llm import find_element, parse_date_to_dt

PORTAL_HOME_SNAPSHOT = """URL: http://localhost:8001/
Title: Vendor Search - Invoice Portal

Page Text:
Search Vendor Invoices Enter vendor name (e.g. Acme, Microsoft, Globex, Initech) to query invoices. Search

Interactive Elements:
[1] input:text "Enter vendor name..." (placeholder: Enter vendor name...)
[2] button "Search"
"""

SEARCH_RESULTS_SNAPSHOT = """URL: http://localhost:8001/search?q=acme
Title: Vendor Search - Invoice Portal

Page Text:
Search Results for "acme" Invoice Number Vendor Issue Date Action INV-2026-001 Acme Technologies 2026-08-15 View Details → INV-2026-003 Acme Technologies 2026-09-30 View Details → INV-2026-005 Acme Tech Pvt Ltd 2026-09-12 View Details →

Interactive Elements:
[1] input:text "Enter vendor name..." (placeholder: Enter vendor name...) (value: acme)
[2] button "Search"
[3] a "View Details →" (href: /invoice/INV-2026-001)
[4] a "View Details →" (href: /invoice/INV-2026-003)
[5] a "View Details →" (href: /invoice/INV-2026-005)
"""


class TestFakeLLMLookup(unittest.TestCase):

    def test_find_search_input(self):
        """Find search input by type and label/placeholder substring."""
        elem_id = find_element(PORTAL_HOME_SNAPSHOT, type_prefix="input", label_substring="vendor")
        self.assertEqual(elem_id, 1)

    def test_find_search_button(self):
        """Find Search button by type and label substring."""
        elem_id = find_element(PORTAL_HOME_SNAPSHOT, type_prefix="button", label_substring="Search")
        self.assertEqual(elem_id, 2)

    def test_find_link_by_href(self):
        """Find link by href substring in search results."""
        elem_id = find_element(SEARCH_RESULTS_SNAPSHOT, type_prefix="a", href_substring="/invoice/INV-2026-003")
        self.assertEqual(elem_id, 4)

    def test_parse_date_formats(self):
        """Support both ISO and human date formats."""
        dt_iso = parse_date_to_dt("2026-09-30")
        self.assertEqual(dt_iso.year, 2026)
        self.assertEqual(dt_iso.month, 9)
        self.assertEqual(dt_iso.day, 30)

        dt_human = parse_date_to_dt("15 September 2026")
        self.assertEqual(dt_human.year, 2026)
        self.assertEqual(dt_human.month, 9)
        self.assertEqual(dt_human.day, 15)


if __name__ == "__main__":
    unittest.main()
