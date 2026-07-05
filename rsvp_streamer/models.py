from dataclasses import dataclass


@dataclass(frozen=True)
class StreamOutput:
    """A single streamed word emitted by :class:`WordStreamer`.

    Instances are immutable value objects — one per word displayed.

    Attributes:
        text: The word being displayed.
        center_index: Index within ``text`` of the optimal recognition
            point (ORP) — the character an RSVP reader fixates on.
        indices: ``(start, end)`` span of the word within the source text,
            with ``end`` exclusive (``source[start:end] == text``).
        char_len: Number of characters in ``text``.
    """

    text: str
    center_index: int
    indices: tuple[int, int]
    char_len: int

    @classmethod
    def from_span(cls, text: str, center_index: int, start: int) -> "StreamOutput":
        """Build an output from a word, its ORP index, and its start offset.

        ``char_len`` and the end of ``indices`` are derived from ``text`` so
        they cannot drift out of sync with it.
        """
        return cls(
            text=text,
            center_index=center_index,
            indices=(start, start + len(text)),
            char_len=len(text),
        )
