# AI Hotel Booking Agent - backend image
FROM python:3.11-slim

# Prevents Python from writing .pyc files and buffers stdout - makes
# container logs show up immediately instead of being buffered.
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

# System packages needed to build some Python deps and for
# faster-whisper's audio handling.
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    ffmpeg \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies first so code changes don't
# force a full dependency reinstall.
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Create an unprivileged application user
RUN useradd --create-home --shell /usr/sbin/nologin appuser

# Run the application as non-root
USER appuser

EXPOSE 8000

# No --reload in production - that's a dev-only convenience flag.
CMD ["sh", "-c", "python -m app.database.seed && uvicorn app.main:app --host 0.0.0.0 --port 8000"]
