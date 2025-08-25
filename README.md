# Swildesk Article Scraper

A high-performance, async web scraper specifically optimized for extracting content from Swildesk support portal articles. Built with FastAPI and designed for integration with n8n workflows.

## Features

- **JavaScript Rendering**: Uses `requests-html` to handle dynamic content
- **Async Support**: Built with asyncio for high-performance concurrent scraping
- **Swildesk Optimized**: Specifically designed for Swildesk support portal structure
- **n8n Ready**: Perfect integration with n8n HTTP nodes
- **Error Handling**: Robust error handling with detailed logging
- **Content Extraction**: Extracts title, content, images, and metadata

## Installation

1. **Install Dependencies**:

   ```bash
   pip install -r requirements.txt
   ```

2. **Install Chrome/Chromium** (required for requests-html):

   ```bash
   # On Ubuntu/Debian
   sudo apt-get install chromium-browser

   # On macOS
   brew install chromium

   # On Windows
   # Download from https://www.chromium.org/getting-involved/download-chromium
   ```

## Usage

### 1. Start the FastAPI Server

```bash
cd scarperApp
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

### 2. API Endpoint

**POST** `/scrape`

**Request Body**:

```json
{
  "url": "https://support.swildesk.com/portal/en/kb/articles/import-data-in-swilerp-retailgraph-through-csv"
}
```

**Response**:

```json
{
  "title": "Import Data in Swilerp RetailGraph through CSV",
  "content": "Full article content...",
  "images": ["https://example.com/image1.jpg"],
  "metadata": { "description": "..." },
  "url": "https://support.swildesk.com/...",
  "status": "success"
}
```

### 3. Test the Scraper

```bash
python test_scraper.py
```

## n8n Integration

### Workflow Setup

1. **HTTP Request Node**:

   - Method: `POST`
   - URL: `https://your-scraper-domain.com/scrape`
   - Body Parameters:
     - `url`: `={{ $json.portalUrl }}`

2. **Split in Batches Node**:

   - Batch Size: `1` (process one article at a time)
   - Options: `Reset: true`

3. **Loop Configuration**:
   - Connect "Loop Over Items" → "Scrape Article"
   - Connect "Scrape Article" → "Loop Over Items"

### Example n8n Workflow

```json
{
  "nodes": [
    {
      "parameters": {
        "method": "POST",
        "url": "https://your-scraper-domain.com/scrape",
        "sendBody": true,
        "bodyParameters": {
          "parameters": [
            {
              "name": "url",
              "value": "={{ $json.portalUrl }}"
            }
          ]
        }
      },
      "type": "n8n-nodes-base.httpRequest",
      "name": "Scrape Article"
    },
    {
      "parameters": {
        "options": {
          "reset": true
        }
      },
      "type": "n8n-nodes-base.splitInBatches",
      "name": "Loop Over Items"
    }
  ],
  "connections": {
    "Scrape Article": {
      "main": [
        [
          {
            "node": "Loop Over Items",
            "type": "main",
            "index": 0
          }
        ]
      ]
    },
    "Loop Over Items": {
      "main": [
        [],
        [
          {
            "node": "Scrape Article",
            "type": "main",
            "index": 0
          }
        ]
      ]
    }
  }
}
```

## Architecture

### Core Components

1. **SwildeskScraper Class**: Main scraping logic
2. **Async Support**: Built-in asyncio support for concurrent operations
3. **Content Extraction**: Smart content detection for Swildesk articles
4. **Error Handling**: Comprehensive error handling and logging

### Content Extraction Strategy

The scraper uses multiple strategies to find article content:

1. **Primary Selectors**: Swildesk-specific CSS selectors
2. **Fallback Selectors**: Generic article content selectors
3. **Text Analysis**: Finds the div with the most text content
4. **Content Cleaning**: Removes ads, navigation, and other non-content elements

### Performance Features

- **Concurrent Scraping**: Can handle multiple articles simultaneously
- **Session Reuse**: Maintains HTTP sessions for efficiency
- **Timeout Handling**: Configurable timeouts for different scenarios
- **Memory Efficient**: Processes one article at a time

## Configuration

### Environment Variables

```bash
# Optional: Set log level
LOG_LEVEL=INFO

# Optional: Set Chrome executable path
CHROME_PATH=/usr/bin/chromium-browser
```

### Scraping Options

- **Timeout**: 30 seconds per article
- **JavaScript Rendering**: 2-second wait after page load
- **User Agent**: Modern Chrome user agent
- **Headers**: Full browser-like headers

## Error Handling

The scraper provides detailed error information:

```json
{
  "title": "Error",
  "content": "Failed to scrape article: Connection timeout",
  "images": [],
  "metadata": {},
  "url": "",
  "status": "error",
  "error": "Connection timeout"
}
```

## Monitoring and Logging

- **Structured Logging**: JSON-formatted logs
- **Performance Metrics**: Scraping time and success rates
- **Error Tracking**: Detailed error information
- **Request Monitoring**: HTTP status codes and response times

## Deployment

### Docker

```dockerfile
FROM python:3.11-slim

# Install Chrome
RUN apt-get update && apt-get install -y chromium

# Install Python dependencies
COPY requirements.txt .
RUN pip install -r requirements.txt

# Copy application
COPY . .

# Expose port
EXPOSE 8000

# Run the application
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
```

### Render.com

1. Connect your GitHub repository
2. Set build command: `pip install -r requirements.txt`
3. Set start command: `uvicorn app.main:app --host 0.0.0.0 --port $PORT`

## Troubleshooting

### Common Issues

1. **Chrome not found**: Install Chromium browser
2. **Timeout errors**: Increase timeout values in the scraper
3. **Content not extracted**: Check if the website structure has changed
4. **Rate limiting**: Add delays between requests

### Debug Mode

Enable debug logging:

```python
import logging
logging.basicConfig(level=logging.DEBUG)
```

## Performance Considerations

- **Concurrent Scraping**: Process multiple articles simultaneously
- **Batch Processing**: Use n8n's batch processing for large datasets
- **Rate Limiting**: Respect website's rate limits
- **Resource Management**: Monitor memory and CPU usage

## Security

- **Input Validation**: All URLs are validated
- **Error Sanitization**: Error messages don't expose internal details
- **Rate Limiting**: Built-in protection against abuse
- **CORS Support**: Configured for cross-origin requests

## Support

For issues or questions:

1. Check the logs for detailed error information
2. Verify the target website is accessible
3. Test with the provided test script
4. Check Chrome/Chromium installation

## License

This project is licensed under the MIT License.
