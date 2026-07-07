# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Commands

Everything runs from the repo root (flat package layout; imports resolve via
`pythonpath = ["."]` in `pyproject.toml`).

- Install test deps: `pip install -r requirements.txt` (pytest)
- Run all tests: `python -m pytest` (or `pytest`)
- Run one file / test: `python -m pytest tests/test_player.py` or
  `python -m pytest tests/test_player.py::test_pause_freezes_progress_then_resume_finishes`
- Run the demo: `python -m rsvp_streamer.demo`
- Optional editable install (enables the `rsvp-streamer` console script): `pip install -e .`

Requires Python ≥ 3.10 (uses `X | Y` and `tuple[int, int]` typing).

## Architecture

rsvp-streamer streams text via rapid serial visual presentation (RSVP) — flashing one word at
a time at a controlled rate. The design deliberately separates *what word comes next* from
*when to show it*:

- `rsvp_streamer/streamer.py` — `WordStreamer`, the **timeless iterator core**. Iterating it (or
  calling `step()`) yields `StreamOutput` values with no notion of a clock, which keeps the word
  logic pure and unit-testable. `source`/`rate` are validated properties (rate is words-per-minute;
  `interval` derives seconds-per-word). `_tokenize` produces `(word, start, end)` triples via
  `re.finditer` (`_WORD_RE`) whose spans index back into the source; `_identify_center` computes
  the optimal recognition point (ORP) on the word's alphanumeric core (punctuation doesn't skew
  it; all-punctuation words fall back to raw length) via a Spritz-style pivot table
  (`_ORP_THRESHOLDS`), returning an index into the full token.
- `rsvp_streamer/player.py` — `StreamPlayer`, the **timed layer** on top. It drives a `WordStreamer`
  on a background daemon thread at `interval` seconds/word — or per-word via an optional
  `delay_for(out, base_interval) -> seconds` strategy (`base_interval` is the current
  `interval`, re-read each word so runtime rate changes apply) — with `start/pause/resume/stop/join`.
  `words_played` / `progress` report position for progress bars.
  Concurrency uses three `threading.Event`s: `_stop` (exit), `_resumed` (set=playing, clear=paused),
  `_done` (worker exited). Pause takes effect at the next word boundary; `stop()` interrupts the
  inter-word delay immediately (via `_stop.wait(delay)`) and wakes a parked-while-paused worker.
  `stop()` is safe to call from inside `on_word` (it skips joining its own thread). Exceptions from
  `on_word`/`on_finish`/`delay_for` are captured into `_error`, exposed via `error`, and re-raised by `join()`;
  `_done` is set last so a thread returning from `join()` always sees a populated `_error`.
- `WordStreamer.play(on_word, on_finish=...)` is the convenience path: it constructs and starts a
  `StreamPlayer` and returns it. It imports `StreamPlayer` lazily to avoid an import cycle.
- `rsvp_streamer/models.py` — `StreamOutput`, a frozen value object (`text`, `center_index`,
  `indices`, `char_len`, `trailing`). Build via `StreamOutput.from_span(...)`, which derives
  `char_len` and the span end from `text` so they cannot drift. `trailing` is the whitespace run
  after the word (captured in `WordStreamer.step` from the gap to the next token), so a pacer can
  react to line/paragraph breaks that whitespace tokenisation otherwise discards.
- `rsvp_streamer/cadence.py` — `Cadence`, a frozen, callable `delay_for(out, base)` preset. It maps
  a dict of `multipliers` (word's last char for punctuation; `"long"` past `long_word_len`; `"line"`/
  `"paragraph"` from `out.trailing`) onto the base interval, composing multiplicatively. Overrides
  merge over `DEFAULT_MULTIPLIERS`.
- `rsvp_streamer/exceptions.py` — `StreamError`, raised for invalid config/state.
- `rsvp_streamer/demo.py` — runnable example that streams a sentence with the ORP pinned to a fixed
  column; drives the timed player.

## Testing notes

Tests are `pytest` (pinned in `requirements.txt`). The player tests in `tests/test_player.py`
are the delicate ones — they exercise a background thread — so they are written to avoid
wall-clock flakiness:

- `Rendezvous` gates the worker one word at a time (the `on_word` callback blocks until the test
  calls `allow()`), making the pause/resume test fully deterministic rather than sleep-based.
- The stop test uses a deliberately huge inter-word interval (`rate=SLOW`) that `stop()` interrupts
  instantly, giving a large timing margin while still running in milliseconds.

When touching threading in `StreamPlayer`, preserve these properties: pause/resume act at word
boundaries, and `stop()` interrupts the inter-word delay immediately (via `_stop.wait(delay)`) —
including custom dwells returned by `delay_for`.
