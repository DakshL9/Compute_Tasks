"""
image_utils.py
---------------
One small, focused job: look at whatever the user typed and figure out
whether it contains a local image file path -- so the chat loop can
decide "is this a normal message, or does it include a photo?" without
the user ever having to type a special command like /analyze.

How the detection works:
We use a regular expression (regex) -- a pattern-matching tool built into
Python's `re` module for finding text that follows a certain shape,
rather than text that's an exact known string. That's exactly what a
file path is: we don't know the path in advance, but we DO know the
*shape* it takes (e.g. "a drive letter, then a colon and backslash, then
some characters, ending in .jpg").

The pattern below matches two shapes:
  - Windows paths:  C:\\Users\\Daksh\\Pictures\\lunch.jpg
  - Unix paths:     /home/user/Pictures/lunch.jpg

Critically, the Windows pattern allows SPACES inside the path (e.g.
"D:\\VS CODE\\Compute Tasks\\LLM2\\salad.jpg"), because real Windows
folder names very often contain spaces ("Program Files", "My Documents",
and so on). An earlier version of this function split the message on
whitespace first, which broke paths like that into unmatched fragments
-- this version fixes that by matching the whole path shape directly
instead of guessing token-by-token.

The match is "lazy" (matches as little as possible) and stops the moment
it reaches a supported extension, so it won't accidentally swallow the
rest of the sentence. A trailing check ((?!\\w)) makes sure we stopped at
a real extension boundary (so "salad.jpgish" won't be mistaken for
"salad.jpg").
"""

import re

from src.config import SUPPORTED_IMAGE_EXTENSIONS

# Build "jpg|jpeg|png|webp" from the configured extensions (which are
# stored with a leading dot, e.g. ".jpg").
_EXTENSION_ALTERNATION = "|".join(
    re.escape(ext.lstrip(".")) for ext in SUPPORTED_IMAGE_EXTENSIONS
)

_IMAGE_PATH_RE = re.compile(
    r"(?P<path>"
    r"[A-Za-z]:\\[^\n\"']+?\.(?:" + _EXTENSION_ALTERNATION + r")"  # Windows
    r"|"
    r"/[^\s\"']+?\.(?:" + _EXTENSION_ALTERNATION + r")"             # Unix
    r")(?!\w)",
    re.IGNORECASE,
)

# Punctuation that can be left dangling right where the path used to be
# (e.g. the "..." in "...salad.jpg...will this be healthy").
_EDGE_PUNCTUATION = re.compile(r"^[\s.,;:\-]+|[\s.,;:\-]+$")


def extract_image_path(user_input):
    """
    Look for a local image path inside `user_input`.

    Returns a tuple: (image_path_or_None, remaining_text)
    - If no image path is found, returns (None, user_input) unchanged.
    - If one is found, returns (path, text_with_path_removed).
    """
    match = _IMAGE_PATH_RE.search(user_input)
    if not match:
        return None, user_input

    path = match.group("path")
    remaining = user_input[: match.start()] + user_input[match.end():]
    remaining = _EDGE_PUNCTUATION.sub("", remaining).strip()

    return path, remaining
