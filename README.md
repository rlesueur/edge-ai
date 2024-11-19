# OpenAI-Compatible Ollama Vision API

This is a Flask-based API server that provides OpenAI-compatible endpoints for both vision and text completion tasks using Ollama and the llama3.2-vision model.

## Prerequisites

1. Install Ollama from https://ollama.ai/
2. Make sure you have the llama3.2-vision model:
```bash
ollama pull llama3.2-vision:11b-instruct-fp16
```

## Installation

1. Create a virtual environment and activate it:
```bash
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

2. Install dependencies:
```bash
pip install -r requirements.txt
```

## Running the Server

1. Start Ollama in a separate terminal:
```bash
ollama serve
```

2. Start the API server:
```bash
python app.py
```

The server will start on port 8000 by default. You can change this by setting the PORT environment variable.

## API Usage

### Text Completion
```python
import requests

response = requests.post(
    "http://localhost:8000/v1/chat/completions",
    json={
        "model": "llama3.2-vision:11b-instruct-fp16",
        "messages": [
            {"role": "user", "content": "What is the capital of France?"}
        ],
        "temperature": 0.7
    }
)
print(response.json())
```

### Vision Tasks
```python
import requests
import base64

# Function to encode image to base64
def encode_image(image_path):
    with open(image_path, "rb") as image_file:
        return base64.b64encode(image_file.read()).decode('utf-8')

# Get base64 string of image
image = encode_image("path/to/your/image.jpg")

response = requests.post(
    "http://localhost:8000/v1/chat/completions",
    json={
        "model": "llama3.2-vision:11b-instruct-fp16",
        "messages": [
            {
                "role": "user",
                "content": [
                    "What's in this image?",
                    {
                        "type": "image_url",
                        "image_url": f"data:image/jpeg;base64,{image}"
                    }
                ]
            }
        ]
    }
)
print(response.json())
```

You can also use image URLs directly:
```python
response = requests.post(
    "http://localhost:8000/v1/chat/completions",
    json={
        "model": "llama3.2-vision:11b-instruct-fp16",
        "messages": [
            {
                "role": "user",
                "content": [
                    "What's in this image?",
                    {
                        "type": "image_url",
                        "image_url": "https://example.com/image.jpg"
                    }
                ]
            }
        ]
    }
)
print(response.json())
```

## Public Hosting

To make the API publicly accessible:

1. Start the Flask server:
```bash
python app.py
```

2. In a new terminal, create a tunnel using cloudflared:
```bash
cloudflared tunnel --url http://localhost:8000
```

3. Cloudflared will provide you with a public URL (e.g., `https://something.trycloudflare.com`). Use this URL instead of `localhost:8000` in your API calls.

4. Include your API key in the requests:
```python
import requests

headers = {
    "Authorization": f"Bearer your-api-key-here"
}

response = requests.post(
    "https://your-cloudflare-url.trycloudflare.com/v1/chat/completions",
    headers=headers,
    json={
        "model": "llama3.2-vision:11b-instruct-fp16",
        "messages": [
            {"role": "user", "content": "What is the capital of France?"}
        ],
        "temperature": 0.7
    }
)
print(response.json())
```

**Security Notes:**
- Keep your API key secret and never commit it to version control
- Consider implementing rate limiting for production use
- The cloudflared tunnel URL will change each time you restart the tunnel

## Features

- OpenAI-compatible API format
- Support for both vision and text completion tasks
- 128k context length support
- Handles both base64-encoded images and image URLs
- CORS enabled for web applications
- Configurable temperature and model parameters

## Note

This API is designed to be compatible with OpenAI's API format, but it uses Ollama's llama3.2-vision model as the backend. Some features like token counting are not available since Ollama doesn't provide this information.
