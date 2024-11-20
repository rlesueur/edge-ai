import requests
import base64
import json

API_KEY = "QaMMC2AuXaHgoBZxej7TcB4o8_QozPnNbb7cHO-B3g8"

def encode_image(image_path):
    with open(image_path, "rb") as image_file:
        # Read image and encode
        image_data = image_file.read()
        # Convert to base64 without any newlines
        return base64.b64encode(image_data).decode('utf-8').replace('\n', '')

def test_vision_api(image_path, use_local=False):
    # API endpoint
    url = "http://localhost:8000/v1/chat/completions" if use_local else "https://api.rexia.uk/v1/chat/completions"
    
    print(f"\nUsing endpoint: {url}")
    # Encode image
    base64_image = encode_image(image_path)
    print(f"Image encoded, length: {len(base64_image)} bytes")
    
    # Prepare headers
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {API_KEY}"
    }
    
    # Prepare payload
    payload = {
        "model": "llama3.2-vision",
        "messages": [
            {
                "role": "user",
                "content": [
                    {
                        "type": "text",
                        "text": "What's in this image?"
                    },
                    {
                        "type": "image_url",
                        "image_url": {
                            "url": f"data:image/jpeg;base64,{base64_image}"
                        }
                    }
                ]
            }
        ]
    }
    
    # Make request
    print("Sending request...")
    try:
        response = requests.post(url, headers=headers, json=payload, timeout=300)  # 5 minutes timeout
        print(f"Response status: {response.status_code}")
        if response.status_code != 200:
            print(f"Error response: {response.text}")
            print(f"Response headers: {response.headers}")
        else:
            result = response.json()
            if 'choices' in result and len(result['choices']) > 0:
                content = result['choices'][0].get('message', {}).get('content', '')
                print("\nResponse:")
                print(content)
                if 'stats' in result:
                    print("\nStats:", result['stats'])
    except requests.exceptions.Timeout:
        print("Request timed out after 5 minutes")
    except requests.exceptions.RequestException as e:
        print(f"Request failed: {str(e)}")

if __name__ == "__main__":
    # Replace with path to your test image
    image_path = "test.jpg"  # Put your test image in the project directory
    print("\nTesting local endpoint:")
    test_vision_api(image_path, use_local=True)
    print("\nTesting remote endpoint:")
    test_vision_api(image_path, use_local=False)
