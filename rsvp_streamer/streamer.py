import re
from typing import TYPE_CHECKING, Callable, Optional

from .exceptions import StreamError
from .models import StreamOutput

if TYPE_CHECKING:
    from .player import StreamPlayer

# Words are maximal runs of non-whitespace characters.
_WORD_RE = re.compile(r"\S+")

# ORP pivot table: length -> index of the optimal recognition point.
# Sits just left of centre, following the common RSVP (Spritz-style)
# heuristic. Words longer than the last threshold clamp to the final index.
_ORP_THRESHOLDS = ((1, 0), (5, 1), (9, 2), (13, 3))
_ORP_MAX = 4


class WordStreamer:
    """Stream text one word at a time using RSVP.

    The core is a plain iterator with no notion of time: iterating the
    streamer (or calling :meth:`step`) yields :class:`StreamOutput` values.
    Timing is layered on separately by :class:`StreamPlayer`; use
    :meth:`play` for the common case.

    Example:
        >>> streamer = WordStreamer(source="hello world", rate=300)
        >>> [out.text for out in streamer]
        ['hello', 'world']
    """

    def __init__(self, source: str = "", rate: float = 300):
        self.rate = rate      # set via property (validates)
        self.source = source  # setter tokenises and resets the cursor

    # --- configuration ---

    @property
    def rate(self) -> float:
        """Streaming rate in words per minute (WPM)."""
        return self._rate

    @rate.setter
    def rate(self, wpm: float) -> None:
        if wpm <= 0:
            raise StreamError(f"rate must be a positive WPM value, got {wpm!r}")
        self._rate = float(wpm)

    @property
    def source(self) -> str:
        """The source text being streamed."""
        return self._source

    @source.setter
    def source(self, text: str) -> None:
        if not isinstance(text, str):
            raise StreamError(f"source must be a str, got {type(text).__name__}")
        self._source = text
        self._tokens = self._tokenize()
        self._idx = 0

    @property
    def interval(self) -> float:
        """Seconds each word is displayed, derived from :attr:`rate`."""
        return 60.0 / self._rate

    # --- iteration core ---

    def __iter__(self) -> "WordStreamer":
        self.reset()
        return self

    def __next__(self) -> StreamOutput:
        out = self.step()
        if out is None:
            raise StopIteration
        return out

    def __len__(self) -> int:
        return len(self._tokens)

    def step(self) -> Optional[StreamOutput]:
        """Advance one word, or return ``None`` once the source is exhausted."""
        if self._idx >= len(self._tokens):
            return None
        word, start, end = self._tokens[self._idx]
        next_idx = self._idx + 1
        stop = self._tokens[next_idx][1] if next_idx < len(self._tokens) else len(self._source)
        self._idx = next_idx
        return self._generate_output(word, start, self._source[end:stop])

    def reset(self) -> None:
        """Rewind the cursor to the first word."""
        self._idx = 0

    def _tokenize(self) -> list[tuple[str, int, int]]:
        """Split source into ``(word, start, end)`` triples (``end`` exclusive).

        Words are maximal runs of non-whitespace characters; spans index
        back into the original source so callers can highlight in place.
        """
        return [(m.group(), m.start(), m.end()) for m in _WORD_RE.finditer(self._source)]

    def _identify_center(self, word: str) -> int:
        """Return the optimal recognition point (ORP) index within ``word``.

        The pivot is computed on the word's alphanumeric core so surrounding
        punctuation (``"hello,"``, ``'"quote'``) does not skew it; the
        returned index still points into the full ``word``. A word with no
        alphanumeric core (e.g. ``"—"``) pivots on its raw length instead.
        """
        start, end = 0, len(word)
        while start < end and not word[start].isalnum():
            start += 1
        while end > start and not word[end - 1].isalnum():
            end -= 1
        if start == end:  # no alphanumeric core: fall back to the raw word
            start, end = 0, len(word)
        length = end - start
        for threshold, index in _ORP_THRESHOLDS:
            if length <= threshold:
                return start + index
        return start + _ORP_MAX

    def _generate_output(self, word: str, start: int, trailing: str) -> StreamOutput:
        return StreamOutput.from_span(word, self._identify_center(word), start, trailing)

    # --- timed playback ---

    def play(
        self,
        on_word: Callable[[StreamOutput], None],
        *,
        on_finish: Optional[Callable[[], None]] = None,
        delay_for: Optional[Callable[[StreamOutput, float], float]] = None,
    ) -> "StreamPlayer":
        """Start clock-driven playback and return the running :class:`StreamPlayer`.

        Convenience wrapper: constructs a player over this streamer, starts it
        on a background thread, and hands it back so the caller can
        pause/resume/stop or :meth:`~StreamPlayer.join` it. ``delay_for``
        optionally varies the per-word dwell time (see :class:`StreamPlayer`).
        """
        from .player import StreamPlayer  # local import avoids an import cycle

        player = StreamPlayer(self, on_word, on_finish=on_finish, delay_for=delay_for)
        player.start()
        return player
