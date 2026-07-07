"""Configurable per-word dwell timing for :class:`~rsvp_streamer.player.StreamPlayer`.

A flat rate reads unnaturally: real reading slows on long words and pauses at
clause, sentence, and paragraph boundaries. :class:`Cadence` expresses that as a
simple mapping of multipliers applied to the player's base ``interval``.
"""

from dataclasses import dataclass, field
from typing import Mapping

from .models import StreamOutput

# Default multipliers applied to the base interval. Keys are either:
#   * a single character -> matched against the word's *last* character, so
#     trailing punctuation (attached to the token) slows the following pause;
#   * ``"long"``      -> the word is longer than ``Cadence.long_word_len``;
#   * ``"line"``      -> the word is followed by a single line break;
#   * ``"paragraph"`` -> the word is followed by a blank line (2+ newlines).
# Absent keys default to 1.0 (no effect).
DEFAULT_MULTIPLIERS: Mapping[str, float] = {
    ".": 2.0, "!": 2.0, "?": 2.0,   # sentence end
    ",": 1.4, ";": 1.4, ":": 1.4,   # clause break
    "long": 1.5,
    "line": 1.5,
    "paragraph": 2.5,
}


@dataclass(frozen=True)
class Cadence:
    """A ``delay_for`` strategy: ``dwell = base * (matching multipliers)``.

    Usable directly as the ``delay_for`` argument of
    :meth:`~rsvp_streamer.streamer.WordStreamer.play` /
    :class:`~rsvp_streamer.player.StreamPlayer`. Matching multipliers compose
    multiplicatively, so a long word that also ends a paragraph earns both.

    Args:
        long_word_len: A word with more than this many characters gets the
            ``"long"`` multiplier.
        multipliers: Overrides merged over :data:`DEFAULT_MULTIPLIERS`, so
            ``Cadence(multipliers={"paragraph": 4.0})`` tweaks just one value
            while keeping the rest. See that mapping for the recognised keys.

    Example::

        streamer.play(on_word=show, delay_for=Cadence(multipliers={"paragraph": 3.0}))
    """

    long_word_len: int = 9
    multipliers: Mapping[str, float] = field(default_factory=dict)

    def __post_init__(self) -> None:
        merged = {**DEFAULT_MULTIPLIERS, **dict(self.multipliers)}
        object.__setattr__(self, "multipliers", merged)  # frozen: set via object

    def __call__(self, out: StreamOutput, base: float) -> float:
        factor = 1.0
        if out.char_len > self.long_word_len:
            factor *= self.multipliers.get("long", 1.0)
        if out.text:
            factor *= self.multipliers.get(out.text[-1], 1.0)
        newlines = out.trailing.count("\n")
        if newlines >= 2:
            factor *= self.multipliers.get("paragraph", 1.0)
        elif newlines == 1:
            factor *= self.multipliers.get("line", 1.0)
        return base * factor
