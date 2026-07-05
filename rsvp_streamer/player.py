import threading
from typing import TYPE_CHECKING, Callable, Optional

from .exceptions import StreamError
from .models import StreamOutput

if TYPE_CHECKING:
    from .streamer import WordStreamer


class StreamPlayer:
    """Drive a :class:`WordStreamer` on a clock, on a background thread.

    The streamer itself is a timeless iterator; the player adds wall-clock
    pacing at ``streamer.interval`` seconds per word plus playback controls.
    Playback runs on a daemon thread so the calling thread (a UI, a REPL)
    stays responsive; controls are safe to call from that thread.

    Lifecycle::

        player = StreamPlayer(streamer, on_word=print)
        player.start()          # begins ticking in the background
        player.pause()          # halts at the next word boundary
        player.resume()
        player.join()           # block until the stream is exhausted
        player.stop()           # halt early and join the worker

    Args:
        streamer: The word source to play. It is reset when playback starts.
        on_word: Called with each :class:`StreamOutput` as it is displayed.
            Runs on the worker thread — keep it quick and thread-aware. An
            exception raised here aborts playback and is re-raised by
            :meth:`join` (and available via :attr:`error`).
        on_finish: Optional callback invoked once when playback ends, whether
            the stream was exhausted, aborted, or :meth:`stop` was called.
    """

    def __init__(
        self,
        streamer: "WordStreamer",
        on_word: Callable[[StreamOutput], None],
        *,
        on_finish: Optional[Callable[[], None]] = None,
    ):
        self._streamer = streamer
        self._on_word = on_word
        self._on_finish = on_finish

        self._thread: Optional[threading.Thread] = None
        self._stop = threading.Event()      # set -> worker should exit
        self._resumed = threading.Event()   # set -> playing, clear -> paused
        self._done = threading.Event()      # set -> worker has exited
        self._error: Optional[Exception] = None  # exception that aborted playback

    # --- controls ---

    def start(self) -> None:
        """Reset the streamer and begin playback on a background thread."""
        if self.is_alive:
            raise StreamError("player is already running")
        self._streamer.reset()
        self._error = None
        self._stop.clear()
        self._resumed.set()
        self._done.clear()
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()

    def pause(self) -> None:
        """Halt playback at the next word boundary; keep the worker alive."""
        self._resumed.clear()

    def resume(self) -> None:
        """Resume after a :meth:`pause`. No effect if not paused."""
        self._resumed.set()

    def stop(self) -> None:
        """Stop playback and wait for the worker thread to exit.

        Safe to call from within ``on_word`` (i.e. on the worker thread): it
        signals the stop and returns without joining itself, and the worker
        unwinds once ``on_word`` returns.
        """
        self._stop.set()
        self._resumed.set()  # wake the worker if it is parked in pause
        thread = self._thread
        if thread is not None and thread is not threading.current_thread():
            thread.join()

    def join(self, timeout: Optional[float] = None) -> bool:
        """Block until playback finishes; return True if it did, else False.

        If playback was aborted by an exception in ``on_word`` or
        ``on_finish``, that exception is re-raised here once finished.
        """
        finished = self._done.wait(timeout)
        if finished and self._error is not None:
            raise self._error
        return finished

    # --- state ---

    @property
    def is_alive(self) -> bool:
        """Whether the worker thread exists and has not yet exited."""
        return self._thread is not None and self._thread.is_alive()

    @property
    def is_paused(self) -> bool:
        """Whether playback is currently paused."""
        return self.is_alive and not self._resumed.is_set()

    @property
    def is_playing(self) -> bool:
        """Whether words are actively being emitted right now."""
        return self.is_alive and self._resumed.is_set()

    @property
    def error(self) -> Optional[Exception]:
        """Exception that aborted playback, if any; otherwise ``None``."""
        return self._error

    # --- worker ---

    def _run(self) -> None:
        try:
            try:
                while not self._stop.is_set():
                    self._resumed.wait()          # park here while paused
                    if self._stop.is_set():
                        break
                    out = self._streamer.step()
                    if out is None:               # stream exhausted
                        break
                    self._on_word(out)
                    # Interruptible delay: returns True the instant stop() fires.
                    if self._stop.wait(self._streamer.interval):
                        break
            except Exception as exc:              # a callback/streamer error aborts playback
                self._error = exc
            finally:
                if self._on_finish is not None:
                    try:
                        self._on_finish()
                    except Exception as exc:
                        if self._error is None:
                            self._error = exc
        finally:
            # Set last, so a thread waking from join() sees a fully-populated error.
            self._done.set()
