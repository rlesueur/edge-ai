from flask import Flask, request, jsonify, Response
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
MODEL_NAME = "llama3.2-vision:latest"

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

def create_chat_completion(messages, model=MODEL_NAME, temperature=0.7, stream=False, top_p=1.0, n=1, max_tokens=None, presence_penalty=0.0, frequency_penalty=0.0, stop=None):
    # Map OpenAI parameters to Ollama parameters
    options = {
        "temperature": min(max(temperature, 0), 2),  # Clamp between 0-2
        "top_p": min(max(top_p, 0), 1),  # Clamp between 0-1
        "num_predict": max_tokens if max_tokens is not None else -1,
        "stop": stop if stop else [],
        "repeat_penalty": 1.0 + (frequency_penalty / 2.0),  # Map -2 to 2 range to repeat penalty
        "presence_penalty": presence_penalty,  # Ollama supports this directly
        "num_ctx": 96000,  # Maximum context size that reliably uses GPU
    }

    start_time = time.time()
    token_count = 0
    
    response = requests.post(
        f"{OLLAMA_BASE_URL}/api/chat",
        json={
            "model": model,
            "messages": messages,
            "stream": stream,
            "options": options
        },
        stream=stream
    )
    
    if response.status_code != 200:
        raise Exception(f"Error from Ollama API: {response.text}")
    
    if stream:
        def generate():
            nonlocal token_count
            chat_id = f"chatcmpl-{int(time.time())}"
            created = int(time.time())
            
            # Send the first chunk with the role
            first_chunk = {
                "id": chat_id,
                "object": "chat.completion.chunk",
                "created": created,
                "model": model,
                "choices": [{
                    "index": 0,
                    "delta": {
                        "role": "assistant"
                    }
                }]
            }
            yield f"data: {json.dumps(first_chunk)}\n\n"
            
            for line in response.iter_lines():
                if line:
                    try:
                        chunk = json.loads(line)
                        content = chunk["message"].get("content", "")
                        token_count += len(content.split())  # Rough token count
                        
                        # Format chunk to match OpenAI's API
                        response_chunk = {
                            "id": chat_id,
                            "object": "chat.completion.chunk",
                            "created": created,
                            "model": model,
                            "choices": [{
                                "index": 0,
                                "delta": {
                                    "content": content
                                }
                            }]
                        }
                        yield f"data: {json.dumps(response_chunk)}\n\n"
                        
                    except Exception as e:
                        print(f"Error processing chunk: {str(e)}")
                        continue
            
            # Send timing stats
            elapsed_time = time.time() - start_time
            tokens_per_second = token_count / elapsed_time if elapsed_time > 0 else 0
            stats_chunk = {
                "id": chat_id,
                "object": "chat.completion.chunk",
                "created": created,
                "model": model,
                "choices": [{
                    "index": 0,
                    "delta": {
                        "content": f"\n\n[Stats: {token_count} tokens in {elapsed_time:.2f}s = {tokens_per_second:.2f} tokens/s]"
                    }
                }]
            }
            yield f"data: {json.dumps(stats_chunk)}\n\n"
            
            # Send final chunk with finish_reason
            final_chunk = {
                "id": chat_id,
                "object": "chat.completion.chunk",
                "created": created,
                "model": model,
                "choices": [{
                    "index": 0,
                    "delta": {},
                    "finish_reason": "stop"
                }]
            }
            yield f"data: {json.dumps(final_chunk)}\n\n"
            yield "data: [DONE]\n\n"
        
        return Response(generate(), mimetype='text/event-stream')
    
    result = response.json()
    elapsed_time = time.time() - start_time
    token_count = len(result["message"]["content"].split())  # Rough token count
    tokens_per_second = token_count / elapsed_time if elapsed_time > 0 else 0
    
    return {
        "id": f"chatcmpl-{int(time.time())}",
        "object": "chat.completion",
        "created": int(time.time()),
        "model": model,
        "choices": [{
            "index": 0,
            "message": {
                "role": "assistant",
                "content": result["message"]["content"] + f"\n\n[Stats: {token_count} tokens in {elapsed_time:.2f}s = {tokens_per_second:.2f} tokens/s]"
            },
            "finish_reason": "stop"
        }],
        "usage": {
            "prompt_tokens": -1,
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
                "num_ctx": 128000,  # 128k context window
                "num_gpu": 99  # Use all available GPUs
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
    stream = data.get('stream', False)
    top_p = data.get('top_p', 1.0)
    n = data.get('n', 1)
    max_tokens = data.get('max_tokens', None)
    presence_penalty = data.get('presence_penalty', 0.0)
    frequency_penalty = data.get('frequency_penalty', 0.0)
    stop = data.get('stop', None)
    
    # Validate parameters
    if n > 1:
        return jsonify({"error": "Multiple completions (n>1) are not supported"}), 400
    
    if not isinstance(temperature, (int, float)) or temperature < 0 or temperature > 2:
        return jsonify({"error": "temperature must be between 0 and 2"}), 400
        
    if not isinstance(top_p, (int, float)) or top_p < 0 or top_p > 1:
        return jsonify({"error": "top_p must be between 0 and 1"}), 400
        
    if not isinstance(presence_penalty, (int, float)) or presence_penalty < -2.0 or presence_penalty > 2.0:
        return jsonify({"error": "presence_penalty must be between -2.0 and 2.0"}), 400
        
    if not isinstance(frequency_penalty, (int, float)) or frequency_penalty < -2.0 or frequency_penalty > 2.0:
        return jsonify({"error": "frequency_penalty must be between -2.0 and 2.0"}), 400
    
    # Check if this is a vision request
    has_images = any(
        isinstance(msg.get('content'), list) and 
        any(isinstance(item, dict) and item.get('type') == 'image_url' 
            for item in msg['content'])
        for msg in messages
    )
    
    try:
        if has_images:
            if stream:
                return jsonify({"error": "Streaming is not supported for vision requests"}), 400
            return jsonify(process_vision_request(messages, model, temperature))
        else:
            return create_chat_completion(
                messages=messages,
                model=model,
                temperature=temperature,
                stream=stream,
                top_p=top_p,
                n=n,
                max_tokens=max_tokens,
                presence_penalty=presence_penalty,
                frequency_penalty=frequency_penalty,
                stop=stop
            )
    except Exception as e:
        return jsonify({"error": str(e)}), 500

if __name__ == '__main__':
    # Get port from environment variable or default to 8000
    port = int(os.environ.get('PORT', 8000))
    # Listen on all interfaces
    app.run(host='0.0.0.0', port=port)
