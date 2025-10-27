import os
import torch
from sentence_transformers import SentenceTransformer

# ✅ petit boost perf matmul sur Ampere/Hopper (H100)
try:
    torch.set_float32_matmul_precision("high")
except Exception:
    pass

# device GPU isolé par la config Compose (gpus: device=0/1)
_device = "cuda" if torch.cuda.is_available() and os.getenv("USE_GPU", "1") != "0" else "cpu"
_model_name = os.getenv("EMBED_MODEL", "sentence-transformers/all-MiniLM-L6-v2")
_batch = int(os.getenv("EMBED_BATCH", "64"))

_model = None

def get_embedder():
    global _model
    if _model is None:
        _model = SentenceTransformer(_model_name, device=_device)
    return _model

def embed_any(texts):
    if isinstance(texts, str):
        texts = [texts]
    model = get_embedder()
    with torch.inference_mode():
        vecs = model.encode(
            texts,
            batch_size=_batch,
            convert_to_numpy=True,
            show_progress_bar=False,
            normalize_embeddings=True,
        )
    return vecs
