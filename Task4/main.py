"""
main.py
-------
Entry point for NutriBuddy. Running `python main.py` starts the chat loop.

This file owns the TERMINAL side of things: printing prompts, reading
input, and deciding what kind of message the user just sent. It
deliberately contains almost no "AI logic" -- that all lives in
src/chatbot.py. This separation means you could swap out the terminal
for something else later without touching how the AI itself works.
"""

from src.config import validate_config
from src.chatbot import NutritionCoach
from src.image_utils import extract_image_path

BANNER = """
==================================================
              🥗 NUTRIBUDDY
          AI NUTRITION COACH
==================================================

Hi! I'm NutriBuddy, your friendly AI Nutrition Coach.

I can help you with nutrition questions, healthy
habits, meal ideas, and even analyze meal photos.

Just type a message, or share a meal photo by typing
or pasting its file path (e.g. C:\\Users\\you\\lunch.jpg).

Commands: 'help', 'clear', 'exit' / 'quit'

--------------------------------------------------
"""

HELP_TEXT = """
You can:
  - Ask any nutrition question (meal ideas, macros, habits, etc.)
  - Share a meal photo by including its file path in your message
    (JPG, JPEG, PNG, or WEBP)
  - Type 'clear' to reset the conversation
  - Type 'exit' or 'quit' to leave
"""

EXIT_COMMANDS = {"exit", "quit"}


def main():
    # Why check configuration before starting the loop? Because failing
    # fast with a clear message ("your API key is missing") is far better
    # user experience than starting the chat and only discovering the
    # problem after the user has already typed a question.
    validate_config()

    coach = NutritionCoach()
    print(BANNER)

    # WHY A while LOOP:
    # A chatbot needs to keep asking for input indefinitely -- we don't
    # know in advance how many messages the user will send. A `while True`
    # loop lets the program keep running until the user explicitly decides
    # to leave (by typing exit/quit), at which point we `break` out of it.
    while True:
        try:
            user_input = input("You: ").strip()
        except (EOFError, KeyboardInterrupt):
            # Ctrl+C / Ctrl+D should exit cleanly, not print a traceback.
            print("\n\nGoodbye! Stay healthy. 🥗")
            break

        # --- Empty input: don't waste an API call on nothing ---
        if not user_input:
            print("Please type a message (or 'help' to see what I can do).\n")
            continue

        lowered = user_input.lower()

        # --- Local commands are handled here, never sent to the LLM ---
        if lowered in EXIT_COMMANDS:
            print("\nGoodbye! Stay healthy. 🥗")
            break

        if lowered == "help":
            print(HELP_TEXT)
            continue

        if lowered == "clear":
            coach.clear_history()
            print("Conversation memory cleared. Let's start fresh!\n")
            continue

        # --- Decide: normal message, or does it contain an image path? ---
        image_path, remaining_text = extract_image_path(user_input)

        print()  # blank line before NutriBuddy's reply, for readability
        if image_path:
            print("NutriBuddy is looking at your photo...\n")
            reply = coach.analyze_image(image_path, remaining_text)
            print(f"NutriBuddy:\n\n{reply}\n")
        else:
            reply = coach.get_response(user_input)
            print(f"NutriBuddy: {reply}\n")


if __name__ == "__main__":
    main()
