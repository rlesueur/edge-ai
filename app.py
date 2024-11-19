from flask import Flask, request, jsonify
from flask_cors import CORS
import requests
import base64
from io import BytesIO
from PIL import Image
import json
import time
import os
import signal
import sys
from functools import wraps
from dotenv import load_dotenv
import atexit

# Load environment variables from .env file
load_dotenv()

app = Flask(__name__)
CORS(app)

OLLAMA_BASE_URL = "http://localhost:11434"
MODEL_NAME = "llama3.2-vision:11b-instruct-fp16"

# Get API key from environment variable
API_KEY = os.getenv('API_KEY')
if not API_KEY:
    raise ValueError("API_KEY not found in environment variables")

def require_api_key(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        auth_header = request.headers.get('Authorization')
        if not auth_header:
            return jsonify({"error": "No API key provided"}), 401
        
        # Extract Bearer token
        try:
            api_key = auth_header.split(' ')[1]
        except IndexError:
            return jsonify({"error": "Invalid Authorization header format"}), 401
        
        if api_key != API_KEY:
            return jsonify({"error": "Invalid API key"}), 401
            
        return f(*args, **kwargs)
    return decorated

def create_chat_completion(messages, model=MODEL_NAME, temperature=0.7):
    response = requests.post(
        f"{OLLAMA_BASE_URL}/api/chat",
        json={
            "model": model,
            "messages": messages,
            "stream": False,
            "options": {
                "temperature": temperature,
                "num_ctx": 128000  # 128k context window
            }
        }
    )
    
    if response.status_code != 200:
        raise Exception(f"Error from Ollama API: {response.text}")
    
    result = response.json()
    
    return {
        "id": f"chatcmpl-{int(time.time())}",
        "object": "chat.completion",
        "created": int(time.time()),
        "model": model,
        "choices": [{
            "index": 0,
            "message": {
                "role": "assistant",
                "content": result["message"]["content"]
            },
            "finish_reason": "stop"
        }],
        "usage": {
            "prompt_tokens": -1,  # Ollama doesn't provide token counts
            "completion_tokens": -1,
            "total_tokens": -1
        }
    }

def process_vision_request(messages, model=MODEL_NAME, temperature=0.7):
    processed_messages = []
    
    for message in messages:
        if message.get("role") == "user" and "content" in message:
            content = message["content"]
            if isinstance(content, list):
                text_parts = []
                images = []
                
                for item in content:
                    if isinstance(item, str):
                        text_parts.append(item)
                    elif isinstance(item, dict) and item.get("type") == "image_url":
                        image_url = item["image_url"]
                        if image_url.startswith("data:image"):
                            # Handle base64 encoded images
                            format, imgstr = image_url.split(';base64,')
                            image_data = base64.b64decode(imgstr)
                            img = Image.open(BytesIO(image_data))
                            # Convert to base64 again for Ollama
                            buffered = BytesIO()
                            img.save(buffered, format="JPEG")
                            img_base64 = base64.b64encode(buffered.getvalue()).decode()
                            images.append(f"data:image/jpeg;base64,{img_base64}")
                        else:
                            # Handle regular URLs
                            response = requests.get(image_url)
                            img = Image.open(BytesIO(response.content))
                            buffered = BytesIO()
                            img.save(buffered, format="JPEG")
                            img_base64 = base64.b64encode(buffered.getvalue()).decode()
                            images.append(f"data:image/jpeg;base64,{img_base64}")
                
                processed_messages.append({
                    "role": "user",
                    "content": " ".join(text_parts),
                    "images": images
                })
            else:
                processed_messages.append(message)
        else:
            processed_messages.append(message)
    
    response = requests.post(
        f"{OLLAMA_BASE_URL}/api/chat",
        json={
            "model": model,
            "messages": processed_messages,
            "stream": False,
            "options": {
                "temperature": temperature,
                "num_ctx": 128000  # 128k context window
            }
        }
    )
    
    if response.status_code != 200:
        raise Exception(f"Error from Ollama API: {response.text}")
    
    result = response.json()
    
    return {
        "id": f"chatcmpl-{int(time.time())}",
        "object": "chat.completion",
        "created": int(time.time()),
        "model": model,
        "choices": [{
            "index": 0,
            "message": {
                "role": "assistant",
                "content": result["message"]["content"]
            },
            "finish_reason": "stop"
        }],
        "usage": {
            "prompt_tokens": -1,
            "completion_tokens": -1,
            "total_tokens": -1
        }
    }

def cleanup():
    # Get the process ID
    pid = os.getpid()
    # Find any process listening on port 8000 and terminate it
    os.system(f"lsof -ti:8000 | xargs kill -9 2>/dev/null")

# Register the cleanup function to run on exit
atexit.register(cleanup)

# Handle SIGINT (Ctrl+C) and SIGTERM
def signal_handler(sig, frame):
    print('\nCleaning up...')
    cleanup()
    sys.exit(0)

signal.signal(signal.SIGINT, signal_handler)
signal.signal(signal.SIGTERM, signal_handler)

@app.route('/v1/chat/completions', methods=['POST'])
@require_api_key
def chat_completions():
    data = request.json
    messages = data.get('messages', [])
    temperature = data.get('temperature', 0.7)
    model = data.get('model', MODEL_NAME)
    
    # Check if this is a vision request
    has_images = any(
        isinstance(msg.get('content'), list) and 
        any(isinstance(item, dict) and item.get('type') == 'image_url' 
            for item in msg['content'])
        for msg in messages
    )
    
    try:
        if has_images:
            return jsonify(process_vision_request(messages, model, temperature))
        else:
            return jsonify(create_chat_completion(messages, model, temperature))
    except Exception as e:
        return jsonify({"error": str(e)}), 500

if __name__ == '__main__':
    # Get port from environment variable or default to 8000
    port = int(os.environ.get('PORT', 8000))
    # Listen on all interfaces
    app.run(host='0.0.0.0', port=port)
