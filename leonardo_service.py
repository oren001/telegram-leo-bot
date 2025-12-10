import requests
import json
import time
import os
import config

BASE_URL = "https://cloud.leonardo.ai/api/rest/v1"

def _get_headers():
    return {
        "accept": "application/json",
        "content-type": "application/json",
        "authorization": f"Bearer {config.LEONARDO_API_KEY}"
    }

import logging

def upload_init_image(image_path):
    """
    Uploads an image to Leonardo.ai to be used as an init image.
    Returns the image ID.
    """
    logging.info(f"Starting upload for {image_path}...")
    extension = os.path.splitext(image_path)[1].lower().replace('.', '')
    
    # 1. Get presigned URL
    url = f"{BASE_URL}/init-image"
    payload = {"extension": extension}
    response = requests.post(url, json=payload, headers=_get_headers(), timeout=10)
    if response.status_code != 200:
        raise Exception(f"Failed to get upload URL: {response.text}")
    
    data = response.json()
    upload_url = data['uploadInitImage']['url']
    image_id = data['uploadInitImage']['id']
    fields = json.loads(data['uploadInitImage']['fields'])
    
    # 2. Upload image
    logging.info(f"Uploading bytes to S3 for image {image_id}...")
    with open(image_path, 'rb') as f:
        files = {'file': f}
        response = requests.post(upload_url, data=fields, files=files, timeout=60)
        
    if response.status_code != 204: 
         if response.status_code not in [200, 201, 204]:
            raise Exception(f"Failed to upload image to S3: {response.status_code} {response.text}")
    
    logging.info("Upload complete.")
    return image_id

def generate_image_from_reference(init_image_id, prompt):
    # ... (header same as before)
    """
    Generates an image using an init image.
    Supports V2 API for 'gemini-image-2' (Nano Banana Pro).
    """
    logging.info(f"Requesting generation for init_id={init_image_id}...")
    
    # Use V2 API for Nano Banana Pro
    if config.LEONARDO_MODEL_ID == "gemini-image-2":
        url = f"{BASE_URL.replace('v1', 'v2')}/generations"
        payload = {
            "model": config.LEONARDO_MODEL_ID,
            "parameters": {
                "width": config.IMAGE_WIDTH,
                "height": config.IMAGE_HEIGHT,
                "prompt": prompt,
                "quantity": 1,
                "guidances": {
                    "image_reference": [
                        {
                            "image": {
                                "id": init_image_id,
                                "type": "UPLOADED" 
                            },
                            "strength": "MID" 
                        }
                    ]
                },
            },
            "public": False
        }
    else:
        # Fallback to V1
        url = f"{BASE_URL}/generations"
        payload = {
            "height": config.IMAGE_HEIGHT,
            "width": config.IMAGE_WIDTH,
            "modelId": config.LEONARDO_MODEL_ID,
            "prompt": prompt,
            "init_image_id": init_image_id,
            "init_strength": 0.5,
            "num_images": 1,
            "public": False,
            "tiling": False,
        }
    
    response = requests.post(url, json=payload, headers=_get_headers(), timeout=30)
    if response.status_code != 200:
        raise Exception(f"Failed to start generation: {response.text}")
    
    data = response.json()
    logging.info(f"Generation started. Response: {data}")
    
    if 'sdGenerationJob' in data:
        generation_id = data['sdGenerationJob']['generationId']
    elif 'generate' in data and 'generationId' in data['generate']:
         generation_id = data['generate']['generationId']
    elif 'generationId' in data:
         generation_id = data['generationId']
    else:
         generation_id = data.get('id')
         
    if not generation_id:
         raise Exception(f"Could not find generation ID in response: {data}")

    return _wait_for_generation(generation_id)

def _wait_for_generation(generation_id):
    """
    Polls for generation completion.
    """
    url = f"{BASE_URL}/generations/{generation_id}"
    logging.info(f"polling generation {generation_id}...")
    
    for i in range(120): # Increased to 120 attempts * 2s = 4 mins
        response = requests.get(url, headers=_get_headers(), timeout=10)
        if response.status_code == 200:
            data = response.json()
            generation = data.get('generations_by_pk')
            if not generation:
                 # Sometimes API returns null immediately after creation
                 time.sleep(2)
                 continue
                 
            status = generation['status']
            logging.info(f"Generation status: {status}")
            
            if status == 'COMPLETE':
                images = generation['generated_images']
                if images:
                    return images[0]['url']
            elif status == 'FAILED':
                raise Exception("Generation failed on server side.")
        else:
             logging.warning(f"Poll blocked: {response.status_code}")
        
        time.sleep(2)
        
    raise Exception("Generation timed out.")
