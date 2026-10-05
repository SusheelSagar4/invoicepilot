"""
Invoice Portal Application (Port 8001)
Serves seed vendor invoice data with search capability, invoice details view,
and failure injection (Chaos Switch) endpoints.
"""

from fastapi import FastAPI, Request, Response, status, Query
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel
import os
from .seed_data import INVOICES

app = FastAPI(title="Mock Invoice Portal")

# Jinja2 setup
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
templates = Jinja2Templates(directory=os.path.join(BASE_DIR, "templates"))

# Global chaos switch state
fail_next_count = 0

class ChaosRequest(BaseModel):
    fail_next: int

@app.get("/", response_class=HTMLResponse)
async def home(request: Request):
    """Render home search page without query results."""
    return templates.TemplateResponse(
        request=request,
        name="index.html",
        context={"query": None, "results": None}
    )

@app.get("/search", response_class=HTMLResponse)
async def search_invoices(request: Request, response: Response, q: str = Query(None)):
    """
    Search invoices by vendor name (case-insensitive substring).
    If chaos switch is active, fail_next requests return HTTP 503.
    """
    global fail_next_count

    # Failure Injection Check
    if fail_next_count > 0:
        fail_next_count -= 1
        return templates.TemplateResponse(
            request=request,
            name="503.html",
            context={},
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE
        )

    query_str = (q or "").strip()
    if not query_str:
        return templates.TemplateResponse(
            request=request,
            name="index.html",
            context={"query": "", "results": []}
        )

    # Case-insensitive substring matching on vendor name
    matched_results = [
        inv for inv in INVOICES
        if query_str.lower() in inv["vendor"].lower()
    ]

    return templates.TemplateResponse(
        request=request,
        name="index.html",
        context={"query": query_str, "results": matched_results}
    )

@app.get("/invoice/{invoice_number}", response_class=HTMLResponse)
async def invoice_detail(request: Request, invoice_number: str):
    """Render details page for a specific invoice number."""
    inv = next((i for i in INVOICES if i["invoice_number"].upper() == invoice_number.upper()), None)
    if not inv:
        return HTMLResponse(content="<h1>Invoice Not Found</h1>", status_code=status.HTTP_404_NOT_FOUND)
    
    return templates.TemplateResponse(
        request=request,
        name="detail.html",
        context={"invoice": inv}
    )

@app.post("/admin/chaos")
async def set_chaos(payload: ChaosRequest):
    """
    Enable failure injection for the next N requests to /search.
    JSON payload: {"fail_next": N}
    """
    global fail_next_count
    fail_next_count = payload.fail_next
    return {"status": "chaos_enabled", "fail_next": fail_next_count}

@app.get("/admin/reset")
async def reset_chaos():
    """Clear failure injection state."""
    global fail_next_count
    fail_next_count = 0
    return {"status": "reset", "fail_next": 0}
