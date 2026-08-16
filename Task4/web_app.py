"""
web_app.py
----------
Flask Web Application backend for NutriBuddy — AI Nutrition Coach.

This file serves as the web HTTP layer around the existing NutritionCoach class.
It handles:
- Serving the frontend web interface (HTML/CSS/JS).
- Receiving chat requests (text and/or meal photos) from the browser.
- Session isolation so each browser user has their own independent conversation history.
- Forwarding user input to the server-side NutritionCoach instance.
- Returning AI responses back to the browser as JSON.

Security note: The browser never touches the Groq API key. The key stays
server-side in Python environment variables.
"""

import os
import uuid
import tempfile
from flask import Flask, render_template, request, jsonify, session

from src.config import validate_config, SUPPORTED_IMAGE_EXTENSIONS, MAX_IMAGE_SIZE_BYTES
from src.chatbot import NutritionCoach

# Initialize Flask application
app = Flask(__name__)
app.secret_key = os.getenv("FLASK_SECRET_KEY", "nutribuddy_dev_secret_key_2026")

# Server-side storage for active user conversations.
# Maps session_id (str) -> NutritionCoach instance.
# Why? This ensures that different browser tabs/users do not share conversation
# history, keeping each chat private and isolated.
USER_COACHES = {}


def get_user_coach():
    """
    Retrieve or create a dedicated NutritionCoach instance for the current browser session.
    """
    if "session_id" not in session:
        session["session_id"] = str(uuid.uuid4())
    
    session_id = session["session_id"]
    if session_id not in USER_COACHES:
        USER_COACHES[session_id] = NutritionCoach()
    
    return USER_COACHES[session_id]


@app.route("/")
def index():
    """Render the main single-page chat interface."""
    return render_template("index.html")


@app.route("/api/chat", methods=["POST"])
def chat():
    """
    Main API endpoint for sending messages and/or meal images.

    Accepts:
    - multipart/form-data with optional 'message' (text) and optional 'image' (file upload).

    Returns:
    - JSON object: {"status": "success", "reply": "..."}
      OR {"status": "error", "error": "..."}
    """
    coach = get_user_coach()

    # Extract text message and uploaded file
    user_message = request.form.get("message", "").strip()
    image_file = request.files.get("image")

    # Validation: user must provide either text or an image
    if not user_message and (not image_file or image_file.filename == ""):
        return jsonify({
            "status": "error",
            "error": "Please type a message or upload a meal image."
        }), 400

    # Case 1: Image Upload (with optional text prompt)
    if image_file and image_file.filename != "":
        # Check file extension
        ext = os.path.splitext(image_file.filename)[1].lower()
        if ext not in SUPPORTED_IMAGE_EXTENSIONS:
            return jsonify({
                "status": "error",
                "error": "Unsupported image format. Please upload a JPG, JPEG, PNG, or WEBP image."
            }), 400

        # Save uploaded file to a temporary location on disk so NutritionCoach can read it
        temp_dir = tempfile.gettempdir()
        temp_filename = f"nutribuddy_{uuid.uuid4().hex}{ext}"
        temp_path = os.path.join(temp_dir, temp_filename)

        try:
            image_file.save(temp_path)

            # Check file size (20MB limit)
            file_size = os.path.getsize(temp_path)
            if file_size > MAX_IMAGE_SIZE_BYTES:
                return jsonify({
                    "status": "error",
                    "error": "The uploaded image is too large. Please select an image under 20MB."
                }), 400
            if file_size == 0:
                return jsonify({
                    "status": "error",
                    "error": "The uploaded image appears to be empty."
                }), 400

            # Analyze image using vision model
            reply = coach.analyze_image(temp_path, user_message)
            return jsonify({"status": "success", "reply": reply})

        except Exception as exc:
            # Handle unexpected processing errors gracefully
            return jsonify({
                "status": "error",
                "error": f"An error occurred while processing your image: {str(exc)}"
            }), 500
        finally:
            # Always clean up the temporary file after processing
            if os.path.exists(temp_path):
                try:
                    os.remove(temp_path)
                except OSError:
                    pass

    # Case 2: Text-only message
    else:
        try:
            reply = coach.get_response(user_message)
            return jsonify({"status": "success", "reply": reply})
        except Exception as exc:
            return jsonify({
                "status": "error",
                "error": "Something went wrong while generating a response. Please try again."
            }), 500


@app.route("/api/new-chat", methods=["POST"])
def new_chat():
    """
    Clear the current user's conversation history.
    """
    coach = get_user_coach()
    coach.clear_history()
    return jsonify({
        "status": "success",
        "message": "Conversation history cleared."
    })


if __name__ == "__main__":
    # Validate environment & API keys before starting server
    validate_config()
    
    print("==================================================")
    print("     NUTRIBUDDY WEB APPLICATION")
    print("==================================================")
    print("Server running on http://127.0.0.1:5000")
    print("Press Ctrl+C to stop.")
    print("--------------------------------------------------")
    
    app.run(debug=True, port=5000)
