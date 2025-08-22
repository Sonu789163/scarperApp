## Vision Backend (FastAPI)

A FastAPI backend that provides web scraping, OCR/Caption proxying, and YouTube video processing capabilities. Designed to be called from tools like n8n via simple HTTP requests.

### Endpoints

- `GET /health` — liveness check
- `GET /healthz` — health check for Render deployment
- `POST /proxy/ocr` — multipart form-data with `file` to forward to OCR service; returns `{ text }`
- `POST /proxy/caption` — multipart form-data with `file` to forward to Caption service; returns `{ caption }`
- `POST /scrape` — JSON `{ "url": "https://...", "headless": true }`; returns `{ title, text, images, html, markdown }`
- `POST /transcript` — JSON `{ "video_url": "https://youtube.com/...", "languages": ["en"], "translate_to": null, "try_youtube_data_api": false }`; returns transcript segments
- `POST /frames` — JSON `{ "video_url": "https://youtube.com/...", "method": "interval|scenedetect", "max_frames": 100, "return_zip": true }`; returns frame timestamps or ZIP file

### Configuration

Copy `.env.example` to `.env` and set values:

```
APP_OCR_API_URL=http://localhost:8000/ocr
APP_CAPTION_API_URL=http://localhost:8001/caption
APP_REQUEST_TIMEOUT_SECONDS=30
YOUTUBE_API_KEY=your_api_key_here  # Optional, for YouTube Data API fallback
```

### Local development

1. Create virtual env and install deps

```
python -m venv .venv
. .venv/bin/activate  # Windows Git Bash: source .venv/Scripts/activate
pip install -r requirements.txt
```

2. Install FFmpeg (required for video processing)

   - **Windows**: Download from https://ffmpeg.org/download.html
   - **macOS**: `brew install ffmpeg`
   - **Ubuntu/Debian**: `sudo apt install ffmpeg`

3. Run the app

```
uvicorn app.main:app --reload --host 0.0.0.0 --port 8080
```

4. Open docs at `http://localhost:8080/docs`

### Docker

Build and run:

```
docker build -t scarper-app .
docker run --rm -p 8080:8080 --env-file .env scarper-app
```

### n8n integration

#### Web Scraping

- Method: POST
- URL: `http://<host>:8080/scrape`
- JSON Body: `{ "url": "https://example.com/article" }`

#### YouTube Transcript

- Method: POST
- URL: `http://<host>:8080/transcript`
- JSON Body: `{ "video_url": "https://youtube.com/watch?v=VIDEO_ID", "languages": ["en"], "try_youtube_data_api": false }`

#### YouTube Frame Extraction

- Method: POST
- URL: `http://<host>:8080/frames`
- JSON Body: `{ "video_url": "https://youtube.com/watch?v=VIDEO_ID", "method": "scenedetect", "max_frames": 50, "return_zip": true }`

#### OCR/Caption Proxying

- Method: POST
- URLs: `http://<host>:8080/proxy/ocr` and `/proxy/caption`
- Send Binary Data: true → Binary Property: your image key

### YouTube Processing Features

- **Transcript Extraction**: Uses youtube-transcript-api with language fallbacks and translation support
- **Frame Extraction**: Two methods:
  - **Interval**: Extract frames at regular time intervals
  - **Scene Detection**: Use PySceneDetect to find scene changes and extract frames at midpoints
- **Output Options**: JSON with timestamps or ZIP file with actual frame images
- **Safety Limits**: Maximum 500 frames, configurable thresholds

### Deployment options

#### Option A: Docker on a VM (Ubuntu, Windows Server)

1. Copy project and `.env` to the server
2. `docker build -t scarper-app .`
3. `docker run -d --name scarper-app --restart unless-stopped -p 8080:8080 --env-file .env scarper-app`

Ensure your OCR (`APP_OCR_API_URL`) and Caption (`APP_CAPTION_API_URL`) URLs are reachable from the container.

#### Option B: Render.com

1. Push code to GitHub
2. Connect repository to Render
3. Use provided `render.yaml` for automatic deployment
4. Set environment variables in Render dashboard

#### Option C: Railway / Fly.io

Use Dockerfile; the app will automatically use the platform's PORT environment variable.

### Notes

- This app is a proxy for OCR/Caption services; it does not run those models itself
- YouTube processing requires FFmpeg (included in Docker image)
- For production, restrict CORS and add authentication if exposing publicly
- Video processing can be resource-intensive; monitor memory usage in production
