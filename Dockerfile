# ==============================================================================
# Stage 1: Build the React 19 Frontend
# ==============================================================================
FROM node:20-alpine AS frontend-builder

WORKDIR /build

# Install dependencies
COPY app/frontend/package*.json ./
RUN npm ci --prefer-offline --no-audit

# Copy source and build static bundle
COPY app/frontend/ ./
RUN npm run build

# ==============================================================================
# Stage 2: Python Backend & Unified Runtime
# ==============================================================================
FROM python:3.11-slim-bookworm AS runner

# Install system dependencies:
# - curl: for container healthchecks
# - ffmpeg & libgomp1: required for faster-whisper local STT and PyTorch inference
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    ffmpeg \
    libgomp1 \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Environment variables
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PORT=8000 \
    AGRISMART_MONGO_URL="mongomock://localhost" \
    AGRISMART_DATABASE_URL="sqlite+aiosqlite:////app/data_store/agrismart.db" \
    AGRISMART_UPLOADS_DIR="/app/uploads"

# Install CPU PyTorch first (drastically reduces image size from >2.5GB to <800MB)
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir torch torchvision --index-url https://download.pytorch.org/whl/cpu

# Install backend Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy backend application, model artifacts, and reference data
COPY app/ ./app/
COPY model/ ./model/
COPY data/ ./data/
COPY docs/ ./docs/
COPY report/ ./report/

# Copy compiled frontend from Stage 1 into the location expected by FastAPI
COPY --from=frontend-builder /build/dist ./app/frontend/dist

# Ensure persistence directories exist
RUN mkdir -p /app/data_store /app/uploads

VOLUME ["/app/data_store", "/app/uploads"]

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=15s --retries=3 \
    CMD curl -f http://localhost:8000/api/health || exit 1

CMD ["uvicorn", "app.backend.main:app", "--host", "0.0.0.0", "--port", "8000"]
