FROM nvidia/cuda:12.1.1-cudnn8-runtime-ubuntu22.04

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

# Python + pip + outils (git, ca-certs)
RUN apt-get update && apt-get install -y --no-install-recommends \
    python3 python3-pip python3-venv python3-dev \
    git ca-certificates \
 && rm -rf /var/lib/apt/lists/*

# Dépendances Python
COPY requirements.txt .
# Torch CUDA 12.1 via le repo PyTorch (cu121)
RUN python3 -m pip install --upgrade pip && \
    python3 -m pip install --extra-index-url https://download.pytorch.org/whl/cu121 -r requirements.txt

# Code
COPY . .
EXPOSE 8080

# Uvicorn installé par pip -> présent dans le PATH
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8080"]
