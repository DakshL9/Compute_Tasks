"""
chatbot.py
----------
This module defines the NutritionCoach class: the "brain" of NutriBuddy.

It is responsible for:
- Talking to Groq's text model for normal conversation.
- Talking to Groq's vision model when the user shares a meal photo.
- Keeping track of conversation history so the bot has memory.
- Translating low-level errors (network issues, bad files, API errors)
  into short, human-readable messages.

Nothing in this file touches the terminal directly (no input()/print()
for the main chat loop) except for a couple of small, self-contained
helper prints. The CLI loop itself lives in main.py. Separating "the
logic" from "the terminal interface" is a basic but important design
habit: it means this class could power a different interface later
(web app, GUI, tests) without being rewritten.
"""

import base64
import os

from groq import Groq, APIConnectionError, APIStatusError, APITimeoutError, RateLimitError

from src.config import (
    GROQ_API_KEY,
    TEXT_MODEL,
    VISION_MODEL,
    SUPPORTED_IMAGE_EXTENSIONS,
    MAX_IMAGE_SIZE_BYTES,
)

# ---------------------------------------------------------------------------
# THE SYSTEM PROMPT
# ---------------------------------------------------------------------------
# A "system prompt" is a special message, sent before any user message, that
# tells the model who it is and how to behave for the rest of the
# conversation. The model doesn't have a personality by default -- the
# system prompt is what turns a general-purpose LLM into "NutriBuddy".
SYSTEM_PROMPT = """You are NutriBuddy, a friendly and supportive AI Nutrition Coach.

Your personality:
- Warm, encouraging, non-judgmental, and practical.
- Conversational and concise -- you give useful answers, not lectures.
- Focused on sustainable, realistic habits rather than crash diets or
  extreme restriction.
- You ask a relevant follow-up question when it would genuinely help
  (e.g. budget, time, dietary preferences), but you don't interrogate
  the user.

You can help with: balanced meals, meal planning, healthy snacks,
hydration, protein and fiber intake, fruits and vegetables, budget- and
student-friendly eating, sustainable weight-management habits, and
building consistent routines.

Important boundaries:
- You are not a doctor, dietitian, or medical professional, and you never
  claim to be one.
- You do not diagnose medical conditions or prescribe medication.
- You never encourage starvation, purging, extreme calorie restriction,
  or other dangerous or disordered eating behavior.
- You do not present uncertain or contested claims as settled medical
  fact.
- For medical conditions, serious symptoms, allergies, pregnancy, eating
  disorders, or specialized dietary/medical needs, you gently recommend
  the user speak with an appropriate healthcare professional (a doctor
  or registered dietitian) -- briefly, and only when relevant, not as a
  disclaimer bolted onto every message.

When a user shares a meal photo, you will be given your own earlier
description of what was in the image. Treat that as context about what
the user ate, and feel free to answer follow-up questions about it
(e.g. "is this balanced?") using that context.
"""

# This second prompt is used ONLY for the vision model, only for the single
# request that actually contains the image. It asks for exactly the kind of
# careful, uncertainty-aware analysis the project requires.
IMAGE_ANALYSIS_INSTRUCTIONS = """You are NutriBuddy's meal-photo analyzer.

Look at the food in this image and respond in this general shape:

1. A short list of the foods you can identify, with a rough portion
   estimate for each where reasonable (e.g. "approximately 1 cup").
2. Estimated calories, protein, carbohydrates, and fat for the whole
   meal.
3. A brief, plain-language note about what makes the estimate uncertain
   for THIS image specifically (e.g. hidden oil, sauces, unclear portion
   size) -- only mention what's actually relevant, don't list every
   possible caveat every time.

Rules you must follow:
- These are visual ESTIMATES, not measurements. Never state numbers as if
  they were precisely measured (avoid things like "27.43g protein").
  Prefer rounded numbers or ranges (e.g. "approximately 25-30 g").
- If portion size or ingredients are ambiguous, say so plainly and give a
  wider range rather than a falsely precise number.
- If the image doesn't clearly show food, say that honestly instead of
  guessing.
- Keep the tone friendly and match NutriBuddy's supportive style, but
  keep this specific response focused on the analysis itself.
"""


class NutritionCoach:
    """
    Encapsulates a single conversation with NutriBuddy.

    Why a class (instead of just a handful of loose functions)?
    Because a conversation has STATE -- the message history needs to stick
    around between calls to get_response(). A class lets us bundle that
    state (self.messages) together with the behavior that operates on it
    (get_response, analyze_image, clear_history) in one object, instead of
    passing a growing list of arguments around everywhere.
    """

    def __init__(self):
        # The Groq client is our connection to the GroqCloud API. Creating
        # it once and reusing it (instead of creating a new one per
        # message) is both more efficient and the standard pattern for
        # this SDK.
        self.client = Groq(api_key=GROQ_API_KEY)

        # This list IS the conversation memory. Every user message and
        # every assistant reply gets appended here, and the *whole* list
        # is sent with each new request (see the explanation in
        # get_response). It starts with just the system prompt.
        self.messages = [{"role": "system", "content": SYSTEM_PROMPT}]

    # ------------------------------------------------------------------
    # NORMAL TEXT CONVERSATION
    # ------------------------------------------------------------------
    def get_response(self, user_input):
        """
        Send a normal text message to the text model and return its reply.

        Why do we resend the whole history every time? Groq's API (like
        essentially every LLM API) is STATELESS: the model has no memory
        of earlier requests. Each API call is self-contained -- the model
        only "knows" what's inside the `messages` list of that specific
        request. So to make the bot seem like it remembers the
        conversation, WE keep a running transcript and send the relevant
        part of it back every single time.
        """
        self.messages.append({"role": "user", "content": user_input})

        try:
            completion = self.client.chat.completions.create(
                model=TEXT_MODEL,
                messages=self.messages,
                temperature=0.7,
                max_completion_tokens=2048,
            )
        except Exception as exc:
            # If the call failed, don't leave a dangling user message in
            # history with no reply -- remove it so a retry / next message
            # isn't sent alongside a broken turn.
            self.messages.pop()
            return self._friendly_error_message(exc)

        reply = completion.choices[0].message.content
        self.messages.append({"role": "assistant", "content": reply})
        return reply

    # ------------------------------------------------------------------
    # IMAGE / MEAL-PHOTO ANALYSIS
    # ------------------------------------------------------------------
    def analyze_image(self, image_path, user_message):
        """
        Validate a local image, send it to the vision model along with the
        user's message, and return a nutrition analysis.

        `user_message` is whatever text the user typed alongside the image
        path (it may be empty, e.g. if they just pasted a bare path).
        """
        # --- Step 1: validate the file before we do anything expensive ---
        error = self._validate_image(image_path)
        if error:
            return error

        # --- Step 2: read + encode the image ---
        # An HTTP API request is text/JSON travelling over the internet --
        # it cannot contain a raw pointer to a file on your hard drive.
        # We have to read the image's raw bytes ourselves and turn them
        # into something that fits inside a JSON request. Base64 is a
        # standard scheme that encodes arbitrary binary data (like a JPEG's
        # bytes) as plain ASCII text. Groq's vision endpoint expects that
        # text wrapped in a "data URL", e.g.:
        #   data:image/jpeg;base64,<the encoded text>
        # which is exactly what the code below builds.
        try:
            with open(image_path, "rb") as image_file:
                image_bytes = image_file.read()
            base64_image = base64.b64encode(image_bytes).decode("utf-8")
        except PermissionError:
            return "I don't have permission to read that file. Please check the file's permissions."
        except OSError:
            return "I couldn't read that image file. It may be corrupted or inaccessible."

        mime_type = self._mime_type_for(image_path)
        data_url = f"data:{mime_type};base64,{base64_image}"

        # --- Step 3: build the request and call the vision model ---
        vision_prompt = IMAGE_ANALYSIS_INSTRUCTIONS
        if user_message.strip():
            vision_prompt += f"\n\nThe user also said: \"{user_message.strip()}\""

        try:
            completion = self.client.chat.completions.create(
                model=VISION_MODEL,
                messages=[
                    {
                        "role": "user",
                        "content": [
                            {"type": "text", "text": vision_prompt},
                            {"type": "image_url", "image_url": {"url": data_url}},
                        ],
                    }
                ],
                temperature=0.4,
                # NOTE: for reasoning models, max_completion_tokens covers
                # BOTH the hidden internal reasoning AND the final visible
                # answer combined -- not just the answer. qwen/qwen3.6-27b
                # "thinks" before answering even when reasoning_format is
                # "hidden", so if this budget is too small, the model can
                # burn the whole thing on reasoning and leave nothing for
                # the actual reply, producing an empty response. We give
                # it a generous budget for exactly that reason.
                max_completion_tokens=3072,
                reasoning_format="hidden",
            )
        except Exception as exc:
            return self._friendly_error_message(exc)

        analysis = completion.choices[0].message.content

        # Defensive check: if the model burned its whole token budget on
        # hidden reasoning (see the note above) or returned nothing for
        # any other reason, don't silently show a blank reply -- tell the
        # user plainly what happened and how to fix it.
        if not analysis or not analysis.strip():
            return (
                "I looked at the image but ran out of room to write my full "
                "answer. Please try again -- if this keeps happening, try "
                "asking a shorter question alongside the photo."
            )

        # --- Step 4: fold the result into the TEXT conversation's memory ---
        # A key design decision: we do NOT store the giant base64 image
        # string in self.messages. Two reasons:
        #   1. It would bloat every future request with a huge chunk of
        #      text the text model doesn't even know how to use (the
        #      base64 blob isn't useful to a non-vision model), wasting
        #      tokens (and money/latency) on every later message.
        #   2. The vision model already did the hard work of turning
        #      pixels into words. We just need to remember WHAT it saw,
        #      not the raw image itself.
        # So instead we store a short textual summary of the analysis as
        # if it were a normal assistant reply. That's what lets a later
        # question like "Is this a balanced meal?" work -- the text model
        # sees the earlier analysis in the (much smaller) history and can
        # refer back to it.
        self.messages.append(
            {"role": "user", "content": f"[Shared a meal photo] {user_message.strip()}".strip()}
        )
        self.messages.append({"role": "assistant", "content": analysis})

        return analysis

    # ------------------------------------------------------------------
    # UTILITIES
    # ------------------------------------------------------------------
    def clear_history(self):
        """Reset the conversation back to just the system prompt."""
        self.messages = [{"role": "system", "content": SYSTEM_PROMPT}]

    def _validate_image(self, image_path):
        """
        Run all the local checks we can do BEFORE spending an API call.
        Returns a user-friendly error string, or None if the image is OK.
        """
        if not os.path.isfile(image_path):
            return "I couldn't find that image. Please check that the path is correct."

        ext = os.path.splitext(image_path)[1].lower()
        if ext not in SUPPORTED_IMAGE_EXTENSIONS:
            return "That image format isn't supported. Please use JPG, JPEG, PNG, or WEBP."

        try:
            size = os.path.getsize(image_path)
        except OSError:
            return "I couldn't access that image file. Please check its permissions."

        if size == 0:
            return "That image file appears to be empty or corrupted."

        if size > MAX_IMAGE_SIZE_BYTES:
            return "That image is too large for me to analyze. Please use an image under 20MB."

        return None

    @staticmethod
    def _mime_type_for(image_path):
        ext = os.path.splitext(image_path)[1].lower()
        return {
            ".jpg": "image/jpeg",
            ".jpeg": "image/jpeg",
            ".png": "image/png",
            ".webp": "image/webp",
        }.get(ext, "image/jpeg")

    @staticmethod
    def _friendly_error_message(exc):
        """
        Turn SDK/network exceptions into a short, non-technical message.
        We still keep the original exception around implicitly (it isn't
        swallowed silently -- callers could log `exc` during development),
        but the user never sees a raw traceback.
        """
        if isinstance(exc, RateLimitError):
            return "I'm getting a lot of requests right now (rate limit reached). Please wait a moment and try again."
        if isinstance(exc, APITimeoutError):
            return "That request timed out. Please check your connection and try again."
        if isinstance(exc, APIConnectionError):
            return "I couldn't connect to GroqCloud. Please check your internet connection."
        if isinstance(exc, APIStatusError):
            if exc.status_code == 401:
                return "Your GroqCloud API key looks invalid. Please check the GROQ_API_KEY in your .env file."
            if exc.status_code == 404:
                return "The requested AI model isn't available right now. Please check the model configuration."
            if exc.status_code == 413:
                return "That request was too large for the API to process."
            return f"GroqCloud returned an error (status {exc.status_code}). Please try again in a moment."
        return "Something unexpected went wrong while talking to the AI model. Please try again."
