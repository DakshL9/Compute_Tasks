"""
config.py
---------
This module is responsible for ONE thing: figuring out how the app should
be configured, and making sure that configuration is valid before the rest
of the program tries to use it.

Concretely, that means:
- Loading the GROQ_API_KEY from a .env file (never from source code).
- Defining which Groq model handles normal text chat.
- Defining which Groq model handles image/vision analysis.
- Failing loudly and clearly if something required is missing, instead of
  letting the program crash later with a confusing error deep inside an
  API call.
"""

import os
import sys
from dotenv import load_dotenv

# load_dotenv() reads the .env file in the project root and copies its
# key=value pairs into the process's environment variables (os.environ).
# We call this once, as early as possible, so every other module can just
# use os.environ / os.getenv as if the variables were always there.
load_dotenv()

# --- Model configuration -----------------------------------------------
# Groq hosts many models. Not all of them can "see" images. We therefore
# deliberately use two different model IDs:
#
#   TEXT_MODEL   -> a fast, general-purpose chat model for normal
#                   nutrition conversation.
#   VISION_MODEL -> a multimodal model that accepts image input alongside
#                   text, used only when the user shares a photo.
#
# These values are verified against GroqCloud's current "Supported Models"
# and "Images and Vision" documentation (console.groq.com/docs/models and
# console.groq.com/docs/vision) as of August 2026:
#
#   - openai/gpt-oss-120b is a current Groq *production* text model well
#     suited to conversational reasoning.
#   - qwen/qwen3.6-27b is Groq's current multimodal (vision) model. It
#     accepts image input, is limited to a 20MB request size and a
#     maximum of 5 images per request, and is listed as a *preview*
#     model (meaning Groq could change/retire it with shorter notice than
#     a production model). That's a real limitation worth knowing about,
#     not a bug in this project.
TEXT_MODEL = os.getenv("GROQ_TEXT_MODEL", "openai/gpt-oss-120b")
VISION_MODEL = os.getenv("GROQ_VISION_MODEL", "qwen/qwen3.6-27b")

# --- API key -------------------------------------------------------------
GROQ_API_KEY = os.getenv("GROQ_API_KEY")

# Supported image extensions for meal-photo analysis.
SUPPORTED_IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp"}

# Groq's documented limit for a request containing an image is 20MB.
# We check against this locally so the user gets a friendly message
# instead of waiting for the API to reject the request.
MAX_IMAGE_SIZE_BYTES = 20 * 1024 * 1024  # 20 MB


def validate_config():
    """
    Check that everything the app needs to run is actually present.

    Why this exists: it's much better to tell the user, in plain English,
    "you forgot to set your API key" the moment the program starts than
    to let it crash 40 lines into a conversation with a cryptic
    AuthenticationError. This is called once, from main.py, before the
    chat loop begins.
    """
    if not GROQ_API_KEY:
        print("=" * 50)
        print("Configuration error: GROQ_API_KEY is missing.")
        print("=" * 50)
        print(
            "\nNutriBuddy needs a GroqCloud API key to talk to the AI model.\n"
            "1. Copy '.env.example' to a new file named '.env'\n"
            "2. Open '.env' and paste in your key:\n"
            "   GROQ_API_KEY=your_actual_key_here\n"
            "3. Get a free key at https://console.groq.com/keys\n"
        )
        sys.exit(1)
