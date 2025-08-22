## Web Scraper Backend (FastAPI)

A FastAPI backend that provides web scraping and OCR/Caption proxying capabilities. Designed to be called from tools like n8n via simple HTTP requests.

### Endpoints

- `GET /health` — liveness check
- `GET /healthz` — health check for Render deployment
- `POST /proxy/ocr` — multipart form-data with `file` to forward to OCR service; returns `{ text }`
- `POST /proxy/caption` — multipart form-data with `file` to forward to Caption service; returns `{ caption }`
- `POST /scrape` — JSON `{ "url": "https://...", "headless": true }`; returns `{ title, text, images, html, markdown }`

### Features

- **Web Scraping**: Extract content from web pages with JavaScript rendering support
- **Inline Image Links**: Automatically include image links inline with text where "Reference Image:" appears
- **OCR Proxying**: Forward image files to OCR service for text extraction
- **Caption Proxying**: Forward image files to caption service for image description

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

2. Install Playwright browsers

```
playwright install
```

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

#### OCR/Caption Proxying

- Method: POST
- URLs: `http://<host>:8080/proxy/ocr` and `/proxy/caption`
- Send Binary Data: true → Binary Property: your image key

### Web Scraping Features

- **JavaScript Rendering**: Uses Playwright for dynamic content extraction
- **Content Cleaning**: Automatically removes ads, navigation, and non-content elements
- **Image Extraction**: Collects all images from the page
- **Inline Image Integration**: Places image links inline with text where "Reference Image:" appears
- **Multiple Fallbacks**: Tries JavaScript rendering first, falls back to raw HTML if needed

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
- Web scraping requires Playwright (included in Docker image)
- For production, restrict CORS and add authentication if exposing publicly
- The scraper automatically enhances text by including image links inline where "Reference Image:" appears
