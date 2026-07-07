# RSVP Streamer

A small Python library for **rapid serial visual presentation (RSVP)**, a speed-reading technique displaying text one word at a time, in a fixed spot, so the reader never has to move their eyes.

`rsvp-streamer` separates *what word comes next* from *when to show it*:

- **`WordStreamer`** — a timeless iterator that tokenises text and yields one `StreamOutput` per
  word. It has no notion of a clock, which keeps the word logic simple and testable.
- **`StreamPlayer`** — an optional layer that drives a `WordStreamer` on a background thread at a
  chosen rate, with `pause` / `resume` / `stop` controls.

## Requirements

- Python ≥ 3.10

## Install

From source (not yet on PyPI):

```bash
git clone https://github.com/eliape/rsvp-streamer.git
cd rsvp-streamer
pip install -e .          # installs the package + the `rsvp-streamer` demo command
pip install -r requirements.txt   # test dependencies (pytest)
```

## Quickstart

### 1. Iterate the words yourself (no timing)

Each iteration yields a `StreamOutput` describing one word:

```python
from rsvp_streamer import WordStreamer

streamer = WordStreamer(source="Reading one word at a time.", rate=300)

for out in streamer:
    print(out.text, "->", out.center_index)
# Reading -> 2
# one -> 1
# ...
```

You can also drive it manually with `step()` (returns `None` when exhausted) and `reset()`.

### 2. Let the player handle timing

`play()` starts a background `StreamPlayer` at the streamer's rate and calls your callback for
each word. It returns the running player so you can control it:

```python
from rsvp_streamer import WordStreamer

streamer = WordStreamer(source="Reading one word at a time.", rate=300)

player = streamer.play(on_word=lambda out: print(out.text, flush=True))
player.pause()          # halts at the next word boundary
player.resume()
player.join()           # block until the whole source has streamed
```

> The `on_word` callback runs on the player's worker thread. An exception raised in `on_word` aborts playback and is re-raised by
> `join()` (also readable via `player.error`). Calling `player.stop()` from inside `on_word` is safe.

A complete terminal example lives in [`rsvp_streamer/demo.py`](rsvp_streamer/demo.py); run it with:

```bash
python -m rsvp_streamer.demo
```

## Concepts

### Rate and interval

`rate` is in **words per minute (WPM)**; `interval` is the derived seconds-per-word
(`60 / rate`). Both are validated and a non-positive rate raises `StreamError`.

By default every word dwells for the flat `interval`. Pass `delay_for=` to `play()` or
`StreamPlayer` to vary the dwell per word, a `(StreamOutput, base_interval) -> float`
callable returning seconds, where `base_interval` is the current `interval` (so runtime
rate changes still apply).

The built-in [`Cadence`](rsvp_streamer/cadence.py) preset 
decreases the rate on long words and pauses at clause, sentence, and paragraph breaks. It's driven by a
plain dictionary of multipliers on the base interval:

```python
from rsvp_streamer import Cadence

# defaults slow long words 1.5x, sentences 2x, paragraphs 2.5x, ...
player = streamer.play(on_word=show, delay_for=Cadence())

# tweak just what you want; the rest stay at their defaults
player = streamer.play(on_word=show, delay_for=Cadence(multipliers={"paragraph": 4.0}))
```

You can also supply your own strategy. The multipliers compose multiplicatively:

```python
def dwell(out, base):
    if out.text.endswith((".", "!", "?")):
        return base * 2.0           # let sentences land
    return base * (1.5 if out.char_len > 9 else 1.0)

player = streamer.play(on_word=show, delay_for=dwell)
```

`Cadence` keys off the word's last character (punctuation), its `char_len` (long words),
and `out.trailing` — the whitespace after the word — to detect line (`\n`) and paragraph
(`\n\n`) breaks, which plain whitespace tokenisation would otherwise discard.

### `StreamOutput`

An immutable value object emitted per word:

| Field          | Meaning                                                                   |
| -------------- | ------------------------------------------------------------------------- |
| `text`         | The word being displayed.                                                 |
| `center_index` | Index of the **optimal recognition point (ORP)** — the pivot to fixate on.|
| `indices`      | `(start, end)` span of the word in the source (`source[start:end] == text`). |
| `char_len`     | `len(text)`.                                                              |
| `trailing`     | Whitespace that followed the word (`" "`, `"\n"`, `"\n\n"`, …) — for line/paragraph pauses. |

The ORP is where the eye should rest for fastest recognition — slightly left of centre. Pinning
that character to a fixed column (as the demo does) is what makes RSVP comfortable to read.

## API summary

```text
WordStreamer(source="", rate=300)
    .rate / .source / .interval        configurable properties (validated)
    iter(s) / next(s) / s.step()       yield StreamOutput, or None at the end
    .reset()                           rewind to the first word
    .play(on_word, on_finish=None, delay_for=None)   start a StreamPlayer, return it

StreamPlayer(streamer, on_word, on_finish=None, delay_for=None)
    .start() / .pause() / .resume() / .stop()
    .join(timeout=None) -> bool        block until finished; re-raises a callback error
    .is_alive / .is_paused / .is_playing
    .words_played / .progress          position in the stream (for progress bars)
    .error                             exception that aborted playback, or None

StreamOutput(text, center_index, indices, char_len, trailing="")
Cadence(long_word_len=9, multipliers=DEFAULT_MULTIPLIERS)   delay_for(out, base) preset
StreamError                            invalid configuration or player state
```

## Development

```bash
python -m pytest        # run the test suite
```

The player tests exercise real threads but are written to be deterministic (no reliance on
wall-clock sleeps) — see the notes in `CLAUDE.md`.

## Status & limitations

Early-stage (v0.1). Known simplifications:

- Tokenisation splits on whitespace, so punctuation stays attached to a word and counts toward
  `char_len` (the ORP, however, is computed on the word's alphanumeric core, so it isn't skewed).
- The ORP uses a coarse length-based pivot table rather than a linguistic model.
- `source` is a single in-memory string; there is no streaming-from-file source yet.

Planned improvements (and what's deliberately out of scope) are tracked in
[ROADMAP.md](ROADMAP.md).
