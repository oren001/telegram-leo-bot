import os
from dotenv import load_dotenv

load_dotenv()

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
LEONARDO_API_KEY = os.getenv("LEONARDO_API_KEY")

# Nano Banana Pro (Gemini 2.5 Flash Image)
LEONARDO_MODEL_ID = "gemini-image-2" 

DEFAULT_PROMPT = "put those people in the most fun and funny situation. make it witty exciting and funny for everyone to enjoy."
IMAGE_WIDTH = 1024
IMAGE_HEIGHT = 1024
