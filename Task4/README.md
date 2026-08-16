# AI Nutrition Coach — NutriBuddy

A friendly AI Nutrition Coach available as both a **CLI chatbot** and a **web application**. Ask nutrition questions, get meal advice, and upload photos of your meals for an estimated calorie and macro breakdown — all powered by GroqCloud.

---

## Description

NutriBuddy is built on an **LLM (Large Language Model)** — an AI model trained on enormous amounts of text that can read your message and generate a relevant, human-sounding reply. The app sends your messages to **GroqCloud**, a hosting service that runs open AI models on custom hardware built for very fast inference. That speed is why replies feel almost instant.

Two kinds of interaction are supported, both in the same conversation:

- **Text chat** — ask about meal ideas, protein, budget-friendly eating, healthy habits, macros, etc.
- **Meal photo analysis** — share a photo of your food and NutriBuddy estimates the meal's calories, protein, carbohydrates, and fat (these are **AI estimates**, not measurements — see [Limitations](#limitations)).

---

## Project Structure

```text
Task4/
│
├── main.py              # CLI entry point — python main.py
├── web_app.py           # Flask web server — python web_app.py
│
├── requirements.txt     # Python dependencies
├── .env                 # Your API keys (never committed)
├── .env.example         # Safe template — shows which variables are needed
├── .gitignore
├── README.md
│
├── src/
│   ├── __init__.py
│   ├── chatbot.py       # NutritionCoach class — all AI logic lives here
│   ├── config.py        # Environment variables, model names, limits
│   └── image_utils.py   # CLI image-path detection from typed text
│
├── templates/
│   └── index.html       # Web UI (served by Flask)
│
└── static/
    ├── style.css        # Chat interface styling
    └── script.js        # Browser-side behaviour (fetch, preview, etc.)
```

---

## Features

### Both Versions
- Friendly "NutriBuddy" AI nutrition coach persona
- Powered by GroqCloud for fast model inference
- Conversation memory (the bot remembers earlier messages within a session)
- Meal photo analysis with estimated calorie and macro breakdown
- Secure API key handling via `.env` (never hardcoded)
- Friendly, human-readable error handling

### CLI Version (`main.py`)
- Clean terminal interface
- Include an image file path anywhere in your message to trigger photo analysis
- `help`, `clear`, `exit` / `quit` commands

### Web Version (`web_app.py`)
- ChatGPT-style chat interface in the browser
- 📎 Image attachment button with live preview
- Send image + text or image only
- Starter prompt chips for quick ideas
- "+ New Chat" button clears conversation without reloading the page
- Random quick nutrition tip displayed on load
- Fully responsive — works on desktop, tablet, and mobile

---

## Technologies

| Layer | Technology | Purpose |
|---|---|---|
| AI | GroqCloud API | Hosts and runs the LLM and vision models |
| AI SDK | `groq` Python SDK | Python wrapper around GroqCloud's HTTP API |
| Backend | **Flask** | Python web framework — handles HTTP requests and serves the UI |
| Backend | `python-dotenv` | Loads API keys from `.env` into environment variables |
| Frontend | HTML / CSS / Vanilla JS | Chat interface in the browser |

---

## Prerequisites

- Python 3.10 or higher
- An internet connection (all AI processing happens on GroqCloud's servers)
- A free GroqCloud account and API key

---

## Getting the API Key

1. Go to [console.groq.com](https://console.groq.com) and sign up or log in.
2. Open the [API Keys page](https://console.groq.com/keys).
3. Create a new API key and copy it — GroqCloud only shows it once.

---

## Installation

**Windows:**

```text
python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt
```

**macOS/Linux:**

```text
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

---

## Environment Variables

The app reads its API key from a `.env` file, which is **never** committed to version control (listed in `.gitignore`).

1. Copy `.env.example` to a new file named `.env`.
2. Open `.env` and paste in your real key:

```text
GROQ_API_KEY=your_actual_key_here
```

That's the only required variable. `.env.example` also shows two optional variables (`GROQ_TEXT_MODEL`, `GROQ_VISION_MODEL`) if you want to swap models.

---

## Running

### CLI Version

```text
python main.py
```

The terminal chatbot starts. Type messages and press Enter to chat. Include a local image file path in your message to trigger photo analysis.

### Web Version

```text
python web_app.py
```

Then open your browser and go to:

```text
http://127.0.0.1:5000
```

---

## Architecture

### Why do we need a backend (Flask)?

The browser's JavaScript is **public** — anyone can open DevTools and read it. If JavaScript called the Groq API directly, the `GROQ_API_KEY` would be visible to anyone. Flask acts as a secure intermediary:

```text
Browser (JavaScript)
        ↓  POST /api/chat  (no API key here)
   Flask (Python / web_app.py)
        ↓  uses GROQ_API_KEY from .env
    NutritionCoach (src/chatbot.py)
        ↓
   GroqCloud API
        ↓
    AI Response
        ↓
   Flask returns JSON
        ↓
Browser displays message
```

The Groq API key is only ever read inside Python, never sent to the browser.

### Web Request Flow

**Text message:**

```text
Browser → POST /api/chat (form field: message="...") → Flask
       → NutritionCoach.get_response() → Groq text model → reply
       → Flask JSON response → Browser displays bubble
```

**Meal image + optional text:**

```text
Browser → POST /api/chat (multipart: message="...", image=<file>)
       → Flask saves image to temp file
       → NutritionCoach.analyze_image(temp_path, message)
       → image is Base64-encoded and sent to Groq vision model
       → analysis returned as text → added to conversation history
       → Flask JSON response → Browser displays analysis
       → temp file deleted
```

---

## How Image Analysis Works

```text
User clicks 📎 and selects a meal photo
        ↓
Browser shows a preview (file is NOT uploaded yet)
        ↓
User presses Send
        ↓
JavaScript sends multipart/form-data to POST /api/chat
        ↓
Flask receives the image file and saves it temporarily
        ↓
Python validates: format (JPG/PNG/WEBP), size (< 20MB)
        ↓
Python reads the raw bytes and encodes them as Base64 text
        ↓
Base64 is sent as a "data URL" to Groq's vision-capable model
        ↓
Model identifies foods, estimates portions, estimates macros
        ↓
Analysis text is stored in conversation history (not the image)
        ↓
Flask returns the analysis → Browser displays it as a chat message
        ↓
Temp image file is deleted from the server
```

**Why Base64?** A web API can only receive text (JSON). A photo is binary data (raw bytes). Base64 converts those bytes into plain text characters so they can travel inside a JSON/form request.

**Why multipart/form-data for uploads?** When a browser sends both text *and* a file, it uses `multipart/form-data` — the browser's native format for file uploads. JSON can't carry raw binary files efficiently.

---

## Conversation Memory

The LLM API is **stateless** — each API call is independent. The model has no memory of previous requests. To simulate memory, the app keeps a running list (`self.messages`) of every user message and assistant reply, and sends the **entire list** with every new request. This is how the bot appears to "remember" the conversation.

When you click **+ New Chat** or type `clear`, this list is reset.

For the web app, each browser session gets its own isolated `NutritionCoach` instance, so different users/tabs don't share conversation history.

---

## Text Chat Examples

**CLI:**

```text
You: What are some good high-protein breakfast options?

NutriBuddy: Great question! A few solid options: Greek yogurt with berries,
a couple of eggs with whole-grain toast, or overnight oats made with milk
and peanut butter. Do you usually have time to cook in the morning?

You: I'm a college student and don't have much time.

NutriBuddy: Totally get it — here are some quick, no-cook options...
```

---

## Image Analysis Examples

**Web:** Click 📎, select a meal photo, optionally type a question, and press Send.

**CLI:** Include the image file path anywhere in your message:

```text
You: Can you analyze this meal? C:\Users\Daksh\Pictures\lunch.jpg

NutriBuddy:

🍽️ Meal Analysis

I can identify:
• Rice — approximately 1 cup
• Dal — approximately 1 cup
• Paneer — approximately 100 g
• Mixed vegetables — approximately 1 cup

Estimated nutrition:
Calories:       ~650 kcal
Protein:        ~28 g
Carbohydrates:  ~85 g
Fat:            ~20 g

These are visual estimates. Actual values may vary depending on portion
size, ingredients, cooking oil, sauces, and preparation method.

You: Is this a balanced meal?

NutriBuddy: Pretty balanced! You have a good carb base from the rice,
solid protein from the dal and paneer, and some fibre from the vegetables...
```

---

## Supported Image Formats

- `.jpg` / `.jpeg`
- `.png`
- `.webp`

Images must be under 20MB (GroqCloud's current vision model request limit).

---

## Security

- `GROQ_API_KEY` lives only in your local `.env` file.
- `.env` is listed in `.gitignore` — it is never committed.
- The browser (JavaScript) never receives or uses the API key.
- The Flask backend is the only code that reads the key and communicates with Groq.
- Uploaded images are saved to a temporary file, processed, and immediately deleted.

---

## Limitations

- **Image-based nutrition values are AI estimates, not measurements.** A photo cannot reveal exact food weight, hidden cooking oil, sauces, sugar, or full recipe composition. Treat them as rough guides only.
- Portion size is genuinely difficult to judge from a single photo angle.
- The chatbot is **not** a doctor or registered dietitian and does not provide medical advice, diagnoses, or prescriptions.
- An internet connection is required for every request — nothing runs locally.
- Conversation memory only lasts for the current session; it resets when you stop the app (CLI) or click New Chat / restart the server (web).
- The vision model (`qwen/qwen3.6-27b`) is listed by Groq as a **preview** model, meaning its availability could change with shorter notice than a production model.
- The web version uses server-side in-memory sessions. If the Flask server restarts, all conversation histories are lost. This is intentional for this local/demo application.

---

## Future Improvements

- Persistent user profiles and meal history across sessions
- Integration with a real nutrition/food database for more accurate values
- Barcode scanning for packaged foods
- More accurate portion-size estimation
- User-specific dietary preferences and restrictions
- Database-backed session storage for the web version
