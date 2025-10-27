# app/endpoints/debug_ai.py
from fastapi import APIRouter
import os
try:
    import torch
except Exception:
    torch = None

router = APIRouter()

@router.get("/debug/ai")
def debug_ai():
    cuda_ok = bool(torch and torch.cuda.is_available())
    return {
        "cuda_available": cuda_ok,
        "cuda_count": (torch.cuda.device_count() if cuda_ok else 0),
        "device_name": (torch.cuda.get_device_name(0) if cuda_ok else None),
        "visible": os.environ.get("NVIDIA_VISIBLE_DEVICES"),
        "model": os.getenv("EMBED_MODEL", "sentence-transformers/all-MiniLM-L6-v2"),
        "batch": int(os.getenv("EMBED_BATCH", "64")),
    }
