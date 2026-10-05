# Mock Applications for InvoicePilot

This directory contains two standalone server-rendered FastAPI applications designed to simulate the enterprise environment for the InvoicePilot Playwright agent.

---

## 🚀 How to Run the Applications

Ensure your virtual environment (`.venv`) is activated, then run the two servers in separate PowerShell terminal windows or tabs:

### 1. Invoice Portal (Port 8001)
Serves seed vendor invoice search & detail pages.
```powershell
.venv\Scripts\python.exe -m uvicorn mock_apps.invoice_portal.app:app --host 127.0.0.1 --port 8001 --reload
```
- **URL**: [http://localhost:8001](http://localhost:8001)
- **Admin Chaos Injection**: `POST http://localhost:8001/admin/chaos` with `{"fail_next": N}`
- **Admin Reset**: `GET http://localhost:8001/admin/reset`

---

### 2. Finance System (Port 8002)
Stores submitted invoices into a local SQLite database (`finance.db`).
```powershell
.venv\Scripts\python.exe -m uvicorn mock_apps.finance_system.app:app --host 127.0.0.1 --port 8002 --reload
```
- **URL**: [http://localhost:8002](http://localhost:8002)
- **All Records Table**: [http://localhost:8002/records](http://localhost:8002/records)
- **Verifier API**: `GET http://localhost:8002/api/records/{invoice_number}`
- **Admin Chaos Injection**: `POST http://localhost:8002/admin/chaos` with `{"fail_next": N}`
- **Admin Reset & Clear DB**: `GET http://localhost:8002/admin/reset`
