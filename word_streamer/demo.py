"""Runnable demo: RSVP-stream a sentence with the ORP pinned in place.

Run it directly (e.g. the IDE "Run" button) or as a module:
    python -m word_streamer.demo
"""

if __package__ in (None, ""):
    # Executed as a plain script: only this file's folder is on sys.path, so
    # there is no parent package for a relative import. Put the repo root on
    # the path and import the package by name instead.
    import os
    import sys

    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    from word_streamer import StreamOutput, WordStreamer
else:
    from . import StreamOutput, WordStreamer

# Column the ORP character is pinned to, so the eye never has to move.
_PIVOT_COLUMN = 12


def _render(out: StreamOutput) -> str:
    """Lay a word out so its ORP character sits at ``_PIVOT_COLUMN``."""
    lead = " " * (_PIVOT_COLUMN - out.center_index)
    return f"{lead}{out.text}"


def main() -> None:
    text = (
        "Rapid serial visual presentation streams text one word at a time "
        "so the reader never has to move their eyes."
    )
    streamer = WordStreamer(source=text, rate=300)

    player = streamer.play(
        on_word=lambda out: print(f"\r{_render(out):<40}", end="", flush=True),
    )
    player.join()  # block until the sentence finishes streaming
    print()


if __name__ == "__main__":
    main()
