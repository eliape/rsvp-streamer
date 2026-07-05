import threading
import time

import pytest

from word_streamer import StreamError, StreamPlayer, WordStreamer

SENTENCE = "one two three four five"
WORDS = SENTENCE.split()

# Rates chosen for intent, not guesswork:
#   FAST  -> tiny interval, so playthroughs finish quickly.
#   SLOW  -> huge interval (10s/word). After the first word the worker parks
#            in the inter-word delay; stop() interrupts it instantly, so tests
#            stay fast while leaving a 10s margin against timing flakiness.
FAST = 6000
SLOW = 6


def wait_until(pred, timeout=2.0, poll=0.005):
    """Spin until ``pred()`` is true or ``timeout`` elapses; return the result."""
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if pred():
            return True
        time.sleep(poll)
    return pred()


class Recorder:
    """Non-blocking, thread-safe sink for words emitted on the worker thread."""

    def __init__(self):
        self._lock = threading.Lock()
        self.words = []
        self.finished = threading.Event()

    def on_word(self, out):
        with self._lock:
            self.words.append(out.text)

    def on_finish(self):
        self.finished.set()

    def count(self):
        with self._lock:
            return len(self.words)

    def reset(self):
        with self._lock:
            self.words.clear()
        self.finished.clear()


class Rendezvous:
    """Gate the worker one word at a time for fully deterministic control.

    ``on_word`` blocks until the test calls :meth:`allow`, so emission is
    driven by the test rather than by wall-clock interval timing.
    """

    def __init__(self):
        self._lock = threading.Lock()
        self.words = []
        self._arrived = threading.Semaphore(0)  # worker announces each word
        self._go = threading.Semaphore(0)       # test grants permission to continue

    def on_word(self, out):
        with self._lock:
            self.words.append(out.text)
        self._arrived.release()
        self._go.acquire()

    def next_word(self, timeout=2.0):
        assert self._arrived.acquire(timeout=timeout), "expected a word; none arrived"
        with self._lock:
            return self.words[-1]

    def assert_no_word(self, window=0.3):
        """True if no new word arrives within ``window`` seconds (i.e. frozen)."""
        arrived = self._arrived.acquire(timeout=window)
        if arrived:
            self._arrived.release()  # leave state untouched for a clearer failure
        return not arrived

    def allow(self):
        self._go.release()


def test_plays_every_word_in_order():
    rec = Recorder()
    player = StreamPlayer(WordStreamer(SENTENCE, rate=FAST), rec.on_word, on_finish=rec.on_finish)

    player.start()
    assert player.join(timeout=5), "playback did not finish in time"

    assert rec.words == WORDS
    assert rec.finished.is_set()
    assert not player.is_alive


def test_play_convenience_returns_running_player():
    rec = Recorder()
    player = WordStreamer(SENTENCE, rate=FAST).play(rec.on_word, on_finish=rec.on_finish)
    try:
        assert isinstance(player, StreamPlayer)
        assert player.join(timeout=5)
        assert rec.words == WORDS
    finally:
        player.stop()


def test_stop_halts_before_the_end():
    rec = Recorder()
    player = StreamPlayer(WordStreamer(SENTENCE, rate=SLOW), rec.on_word, on_finish=rec.on_finish)

    player.start()
    assert wait_until(lambda: rec.count() >= 1), "no first word"
    player.stop()  # interrupts the (10s) inter-word delay immediately

    assert not player.is_alive
    assert rec.finished.is_set(), "on_finish must fire on stop"
    assert rec.count() < len(WORDS)


def test_pause_freezes_progress_then_resume_finishes():
    rv = Rendezvous()
    player = StreamPlayer(WordStreamer(SENTENCE, rate=FAST), rv.on_word)

    player.start()
    assert rv.next_word() == "one"     # worker now blocked inside on_word
    player.pause()
    rv.allow()                          # let it finish word 1 and reach the park point

    assert rv.assert_no_word(), "paused player kept emitting words"
    assert player.is_paused

    player.resume()
    for expected in WORDS[1:]:          # drain deterministically to the end
        assert rv.next_word() == expected
        rv.allow()
    assert player.join(timeout=2), "did not finish after resume"
    assert rv.words == WORDS


def test_starting_twice_raises():
    player = StreamPlayer(WordStreamer(SENTENCE, rate=SLOW), lambda out: None)
    player.start()
    try:
        with pytest.raises(StreamError):
            player.start()
    finally:
        player.stop()


def test_can_restart_after_finishing():
    rec = Recorder()
    player = StreamPlayer(WordStreamer(SENTENCE, rate=FAST), rec.on_word)

    player.start()
    assert player.join(timeout=5)
    assert rec.words == WORDS

    rec.reset()                         # a finished player can run again from the top
    player.start()
    assert player.join(timeout=5)
    assert rec.words == WORDS
    player.stop()


def test_on_word_error_is_surfaced_via_join():
    boom = RuntimeError("boom")
    seen = []

    def on_word(out):
        seen.append(out.text)
        if out.text == "two":
            raise boom

    player = StreamPlayer(WordStreamer(SENTENCE, rate=FAST), on_word)
    player.start()

    with pytest.raises(RuntimeError, match="boom"):
        player.join(timeout=5)          # the callback error is re-raised here
    assert player.error is boom
    assert not player.is_alive
    assert seen == ["one", "two"]       # playback aborted at the failing word


def test_stop_from_within_on_word_does_not_deadlock():
    seen = []
    holder = {}

    def on_word(out):
        seen.append(out.text)
        holder["player"].stop()         # called on the worker thread

    player = StreamPlayer(WordStreamer(SENTENCE, rate=FAST), on_word)
    holder["player"] = player
    player.start()

    assert player.join(timeout=5)       # must not hang or raise
    assert not player.is_alive
    assert seen == ["one"]
