import hashlib
from fastapi import APIRouter, UploadFile, File, Depends
from app.core.config import settings
from app.payments.x402_gateway import pay_dep

router = APIRouter(prefix="/parse")

@router.post("/pdf")
async def parse_pdf(file: UploadFile = File(...), _paid=Depends(pay_dep(settings.PRICE_PARSE_PDF_CENTS, endpoint_label="parse_pdf"))):
    data = await file.read()
    checksum = hashlib.sha256(data).hexdigest()[:16]
    return {
        "ok": True,
        "doc": {"filename": file.filename, "bytes": len(data), "sha256_16": checksum},
        "fields": {"invoice_number": "DEMO-0001", "total_ht": 123.45}
    }
