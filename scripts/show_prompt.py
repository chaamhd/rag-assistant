import sys

from app.prompts import build_messages
from app.search import search

DEFAULT_QUESTION = "How can I pin the Python version of a project?"


def main() -> None:
    question = " ".join(sys.argv[1:]) or DEFAULT_QUESTION
    messages = build_messages(question, search(question))
    for message in messages:
        print(f"===== {message['role'].upper()} =====")
        print(message["content"])
        print()


if __name__ == "__main__":
    main()