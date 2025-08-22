FROM mcr.microsoft.com/playwright/python:v1.47.0-jammy

WORKDIR /app

# Install system dependencies including FFmpeg
RUN apt-get update && apt-get install -y --no-install-recommends \
    ffmpeg \
    && rm -rf /var/lib/apt/lists/*

# Upgrade pip and install numpy first to avoid conflicts
RUN pip install --no-cache-dir --upgrade pip setuptools wheel
RUN pip install --no-cache-dir "numpy>=2.0.0"

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY app /app/app

EXPOSE 8080
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8080"]