"""
Finance System Application (Port 8002)
Allows recording invoice processing data into a local SQLite database.
Includes form UI, duplicate invoice detection, verifier API endpoint,
and failure injection (Chaos Switch) controls.
"""

from fastapi import FastAPI, Request, Form, Response, status
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel
import sqlite3
import os
from . import database

app = FastAPI(title="Mock Finance System")

# Jinja2 setup
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
templates = Jinja2Templates(directory=os.path.join(BASE_DIR, "templates"))

# Global chaos switch state
fail_next_count = 0

class ChaosRequest(BaseModel):
    fail_next: int

@app.on_event("startup")
def startup_db():
    """Ensure SQLite table and sequence exist on app launch."""
    database.init_db()

@app.get("/", response_class=HTMLResponse)
async def show_form(request: Request):
    """Render the invoice submission form."""
    return templates.TemplateResponse(request=request, name="form.html", context={})

@app.post("/submit", response_class=HTMLResponse)
async def submit_invoice(
    request: Request,
    invoice_number: str = Form(...),
    vendor: str = Form(...),
    amount: float = Form(...),
    due_date: str = Form(...)
):
    """
    Handle invoice submission form.
    Checks chaos switch, then inserts invoice into SQLite database.
    Renders success page with FIN-XXXX record ID or duplicate error page.
    """
    global fail_next_count

    # Chaos Injection Check
    if fail_next_count > 0:
        fail_next_count -= 1
        return templates.TemplateResponse(
            request=request,
            name="503.html",
            context={},
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE
        )

    try:
        record_id = database.insert_invoice(
            invoice_number=invoice_number,
            vendor=vendor,
            amount=amount,
            due_date=due_date
        )
        return templates.TemplateResponse(
            request=request,
            name="success.html",
            context={"record_id": record_id}
        )
    except sqlite3.IntegrityError:
        # Duplicate invoice number constraint violation
        return templates.TemplateResponse(
            request=request,
            name="duplicate.html",
            context={"invoice_number": invoice_number},
            status_code=status.HTTP_400_BAD_REQUEST
        )

@app.get("/records", response_class=HTMLResponse)
async def list_records(request: Request):
    """Render HTML page listing all recorded invoices in SQLite database."""
    records = database.get_all_records()
    return templates.TemplateResponse(
        request=request,
        name="records.html",
        context={"records": records}
    )

@app.get("/api/records/{invoice_number}")
async def get_record_api(invoice_number: str):
    """
    JSON API for independent verifier.
    Returns stored record dictionary or 404 if not found.
    """
    rec = database.get_record_by_invoice_number(invoice_number)
    if not rec:
        return JSONResponse(
            status_code=status.HTTP_404_NOT_FOUND,
            content={"detail": f"Invoice '{invoice_number}' not found in finance system."}
        )
    return rec

@app.post("/admin/chaos")
async def set_chaos(payload: ChaosRequest):
    """
    Enable failure injection for the next N POST requests to /submit.
    JSON payload: {"fail_next": N}
    """
    global fail_next_count
    fail_next_count = payload.fail_next
    return {"status": "chaos_enabled", "fail_next": fail_next_count}

@app.get("/admin/reset")
async def reset_system():
    """Clear chaos switch state and reset database table."""
    global fail_next_count
    fail_next_count = 0
    database.reset_db()
    return {"status": "reset", "fail_next": 0, "database": "cleared"}
