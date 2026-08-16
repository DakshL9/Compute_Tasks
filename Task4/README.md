# AI Nutrition Coach — GroqCloud LLM

A command-line chatbot that acts as a friendly nutrition coach. It answers
everyday nutrition questions in normal conversation, and can also look at a
photo of your meal and give you an estimated calorie and macro breakdown.

## Description

This application is a **CLI (command-line) chatbot**. There is no window,
no buttons — you talk to it by typing in a terminal, the same way you'd use
a command prompt.

At its core is an **LLM (Large Language Model)** — an AI model trained on
huge amounts of text that can read what you write and generate a relevant,
human-sounding reply. This project doesn't train or host that model itself;
instead it sends your messages to **GroqCloud**, a hosting service that runs
open models (like Meta's, OpenAI's, and Alibaba's) on custom hardware built
for very fast inference (the process of a trained model generating a
response). That speed is why replies from NutriBuddy feel almost instant.

The app supports two kinds of interaction, both in the same conversation:

- **Text chat** — ask about meal ideas, protein, budget-friendly eating,
  healthy habits, and so on.
- **Meal photo analysis** — share the file path to a photo of your food, and
  NutriBuddy identifies the food, estimates portions, and gives an
  **AI-estimated** calorie/macro breakdown (never a precise measurement —
  see [Limitations](#limitations)).

## Features

- CLI chatbot with a clean, readable terminal interface
- A friendly, supportive "NutriBuddy" nutrition coach persona
- Powered by the GroqCloud API for fast inference
- Conversation memory within a session (the bot remembers earlier messages)
- Meal photo analysis — just include an image path in your message, no
  special command needed
- Estimated calories, protein, carbohydrates, and fat from meal photos
- Secure API key handling via a `.env` file (never hardcoded)
- Friendly, human-readable error handling (no raw crash tracebacks)
- Simple `exit` / `quit` / `help` / `clear` commands

## Technologies

- **Python** — the programming language the app is written in.
- **GroqCloud** — the API provider that hosts and runs the AI models.
- **Groq Python SDK (`groq`)** — an official Python package that wraps
  GroqCloud's web API in convenient Python function calls, so you don't
  have to build raw HTTP requests by hand.
- **python-dotenv** — a small package that loads settings (like your API
  key) from a local `.env` file into your program, keeping secrets out of
  your source code.
- **LLM** — the text model that powers normal conversation.
- **Vision/multimodal model** — a model that can accept both text *and* an
  image in the same request, used only for meal-photo analysis.

## Prerequisites

- Python 3.10 or higher
- An internet connection (all AI processing happens on GroqCloud's servers)
- A free GroqCloud account
- A GroqCloud API key

## Getting the API Key

1. Go to [console.groq.com](https://console.groq.com) and sign up or log in.
2. Open the [API Keys page](https://console.groq.com/keys).
3. Create a new API key and copy it somewhere safe — GroqCloud only shows
   it to you once.

## Installation

**Windows:**

```text
python -m venv venv
venv\Scripts\activate
```

**macOS/Linux:**

```text
python3 -m venv venv
source venv/bin/activate
```

Then, with your virtual environment active:

```text
pip install -r requirements.txt
```

## Environment Variables

The app reads its API key from a `.env` file, which is **never** committed
to version control (it's listed in `.gitignore`).

1. Copy `.env.example` to a new file named `.env`.
2. Open `.env` and paste in your real key:

```text
GROQ_API_KEY=your_actual_key_here
```

That's the only required variable. `.env.example` also shows two optional
variables (`GROQ_TEXT_MODEL`, `GROQ_VISION_MODEL`) if you ever want to swap
which Groq models are used.

## Running

```text
python main.py
```

## Text Chat Example

```text
You: What are some good high-protein breakfast options?

NutriBuddy: Great question! A few solid high-protein options: Greek yogurt
with berries and a handful of nuts, a couple of eggs with whole-grain
toast, or overnight oats made with milk and a scoop of peanut butter.
Do you usually have time to cook in the morning, or are you looking for
something more grab-and-go?

You: I'm a college student and don't have much time.

NutriBuddy: Totally get it — here are some quick, no-cook options:
Greek yogurt cups, a protein shake with milk, or hard-boiled eggs made
in a batch on Sunday so they're ready all week...
```

## Image Analysis Example

You don't need a special command — just include the image's file path
anywhere in your message:

```text
You: Can you estimate the macros in this meal?
C:\Users\Daksh\Pictures\lunch.jpg

NutriBuddy:

🍽️ Meal Analysis

I can identify the following foods:
• Cooked rice — approximately 1 cup
• Dal — approximately 1 cup
• Paneer — approximately 100 g
• Mixed vegetables — approximately 1 cup

Estimated nutrition:
Calories:       ~650 kcal
Protein:        ~28 g
Carbohydrates:  ~85 g
Fat:            ~20 g

These are visual estimates rather than measured values. The actual
nutrition may vary depending on portion size, ingredients, cooking oil,
sauces, and preparation method.

You: Is this a balanced meal?

NutriBuddy: Pretty balanced! You've got a good carb base from the rice,
solid protein from the dal and paneer, and some vegetables in the mix...
```

## Supported Image Formats

- `.jpg`
- `.jpeg`
- `.png`
- `.webp`

Images must be under 20MB, matching GroqCloud's current vision-model
request limit.

## How Image Analysis Works

```text
You type a message containing an image path
        ↓
Python detects the path inside your text
        ↓
Python checks the file exists and is a supported format
        ↓
Python reads the image's raw bytes and encodes them as Base64 text
        ↓
The Base64 text is sent (as a "data URL") to Groq's vision-capable model
        ↓
The model identifies foods, estimates portions, and estimates macros
        ↓
NutriBuddy prints the analysis, and a short summary joins the
conversation's memory for follow-up questions
```

A regular web API can't reach into your computer and read a file directly
— it only understands text sent to it over the internet. That's why the
image has to be converted into Base64 (a way of representing binary data,
like a photo's bytes, using only plain text characters) before it can be
included in the request.

## Security

Your API key lives only in your local `.env` file, which is excluded from
version control by `.gitignore`. It is loaded at runtime with
`python-dotenv` and is never written into source code, printed to the
terminal, or logged. `.env.example` contains only a placeholder, never a
real key.

## Limitations

- **Image-based nutrition values are AI estimates, not measurements.** A
  photo cannot reveal exact food weight, hidden cooking oil, sauces, sugar,
  or full recipe composition.
- Portion size is genuinely difficult to judge from a single photo angle.
- The chatbot is **not** a doctor or registered dietitian and does not
  provide medical advice, diagnoses, or prescriptions.
- An internet connection is required for every request — nothing runs
  locally.
- Conversation memory only lasts for the current run of the program; it
  resets when you close the app (or type `clear`).
- The vision model (`qwen/qwen3.6-27b`) is currently listed by Groq as a
  **preview** model, meaning its availability could change with shorter
  notice than a production model.

## Future Improvements

- Persistent user profiles across sessions
- Integration with a real nutrition/food database for more accurate values
- Barcode scanning for packaged foods
- More accurate portion-size estimation (e.g. reference-object detection)
- User-specific dietary preferences and restrictions
- Meal history and macro tracking over time
- A web or mobile interface
- Database storage instead of in-memory-only history
