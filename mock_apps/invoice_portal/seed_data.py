"""
Seed data for the Invoice Portal.
Contains ~12 seed invoices with vendors, including distractors like 'Acme Technologies' vs 'Acme Tech Pvt Ltd'.
Notice that dates are deliberately not sorted in chronological order so that the agent must reason to find the latest invoice.
"""

INVOICES = [
    {
        "invoice_number": "INV-2026-001",
        "vendor": "Acme Technologies",
        "issue_date": "2026-08-15",
        "total_payable_str": "₹45,200",
        "payment_due_str": "15 September 2026",
        "status": "Paid"
    },
    {
        "invoice_number": "INV-2026-002",
        "vendor": "Microsoft India",
        "issue_date": "2026-09-20",
        "total_payable_str": "₹1,28,000",
        "payment_due_str": "20 October 2026",
        "status": "Unpaid"
    },
    {
        "invoice_number": "INV-2026-003",
        "vendor": "Acme Technologies",
        "issue_date": "2026-09-30",
        "total_payable_str": "₹62,400",
        "payment_due_str": "30 October 2026",
        "status": "Unpaid"
    },
    {
        "invoice_number": "INV-2026-004",
        "vendor": "Globex Corp",
        "issue_date": "2026-07-10",
        "total_payable_str": "₹18,900",
        "payment_due_str": "10 August 2026",
        "status": "Paid"
    },
    {
        "invoice_number": "INV-2026-005",
        "vendor": "Acme Tech Pvt Ltd",
        "issue_date": "2026-09-12",
        "total_payable_str": "₹89,000",
        "payment_due_str": "12 October 2026",
        "status": "Unpaid"
    },
    {
        "invoice_number": "INV-2026-006",
        "vendor": "Initech",
        "issue_date": "2026-08-01",
        "total_payable_str": "₹34,500",
        "payment_due_str": "01 September 2026",
        "status": "Paid"
    },
    {
        "invoice_number": "INV-2026-007",
        "vendor": "Acme Technologies",
        "issue_date": "2026-06-18",
        "total_payable_str": "₹12,000",
        "payment_due_str": "18 July 2026",
        "status": "Paid"
    },
    {
        "invoice_number": "INV-2026-008",
        "vendor": "Microsoft India",
        "issue_date": "2026-08-25",
        "total_payable_str": "₹95,000",
        "payment_due_str": "25 September 2026",
        "status": "Paid"
    },
    {
        "invoice_number": "INV-2026-009",
        "vendor": "Acme Technologies",
        "issue_date": "2026-09-05",
        "total_payable_str": "₹53,800",
        "payment_due_str": "05 October 2026",
        "status": "Unpaid"
    },
    {
        "invoice_number": "INV-2026-010",
        "vendor": "Globex Corp",
        "issue_date": "2026-09-15",
        "total_payable_str": "₹27,600",
        "payment_due_str": "15 October 2026",
        "status": "Unpaid"
    },
    {
        "invoice_number": "INV-2026-011",
        "vendor": "Initech",
        "issue_date": "2026-09-28",
        "total_payable_str": "₹74,000",
        "payment_due_str": "28 October 2026",
        "status": "Unpaid"
    },
    {
        "invoice_number": "INV-2026-012",
        "vendor": "Microsoft India",
        "issue_date": "2026-07-04",
        "total_payable_str": "₹2,10,000",
        "payment_due_str": "04 August 2026",
        "status": "Paid"
    }
]
