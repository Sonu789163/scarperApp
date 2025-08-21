## Vision Backend (FastAPI)

A small FastAPI backend that proxies to your local OCR and Image Captioning services. Designed to be called from tools like n8n via simple HTTP requests.

### Endpoints

- `GET /health` — liveness check
- `POST /proxy/ocr` — multipart form-data with `file` to forward to OCR service; returns `{ text }`
- `POST /proxy/caption` — multipart form-data with `file` to forward to Caption service; returns `{ caption }`
- `POST /scrape` — JSON `{ "url": "https://...", "headless": true }`; returns `{ title, text, images }`

### Configuration

Copy `.env.example` to `.env` and set values:

```
APP_OCR_API_URL=http://localhost:8000/ocr
APP_CAPTION_API_URL=http://localhost:8001/caption
APP_REQUEST_TIMEOUT_SECONDS=30
```

### Local development

1. Create virtual env and install deps

```
python -m venv .venv
. .venv/bin/activate  # Windows Git Bash: source .venv/Scripts/activate
pip install -r requirements.txt
```

2. Run the app

```
uvicorn app.main:app --reload --host 0.0.0.0 --port 8080
```

3. Open docs at `http://localhost:8080/docs`

### Docker

Build and run:

```
docker build -t vision-backend .
docker run --rm -p 8080:8080 --env-file .env vision-backend
```

### n8n integration

- Scrape:

  - Method: POST
  - URL: `http://<host>:8080/scrape`
  - JSON Body: `{ "url": "https://example.com/article" }`

- OCR: HTTP Request node

  - Method: POST
  - URL: `http://<host>:8080/proxy/ocr`
  - Send Binary Data: true → Binary Property: `data` (or your image property name)
  - Header: `Content-Type: multipart/form-data` (n8n sets automatically when Send Binary Data is true)

- Caption: same as OCR but URL `http://<host>:8080/proxy/caption`

Embeddings should be handled in n8n directly if needed; this backend focuses only on OCR and Caption proxying.

### Deployment options

#### Option A: Docker on a VM (Ubuntu, Windows Server)

1. Copy project and `.env` to the server
2. `docker build -t vision-backend .`
3. `docker run -d --name vision-backend --restart unless-stopped -p 8080:8080 --env-file .env vision-backend`

Ensure your OCR (`APP_OCR_API_URL`) and Caption (`APP_CAPTION_API_URL`) URLs are reachable from the container. If they are also containers, you can deploy them on the same Docker network and reference by container name.

#### Option B: Render.com

1. Create a new Web Service
2. Runtime: Docker
3. Build Command: `docker build -t vision-backend .`
4. Start Command: `uvicorn app.main:app --host 0.0.0.0 --port 8080`
5. Add environment variables from `.env`

#### Option C: Railway / Fly.io

Use Dockerfile; set `PORT=8080` where required. Map incoming port to 8080.

### Notes

- This app is a proxy; it does not run OCR/Caption models itself. Make sure those services are deployed and reachable.
- For production, restrict CORS and add authentication (e.g., simple API key header) if exposed publicly.
