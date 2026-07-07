# Roadmap

Prioritized backlog of improvements identified in a code audit (2026-07-05). The code
carries no literal `TODO` markers; these items come from the README's "Status &
limitations" section plus a review of the source. Items are ordered P1 (do first) to
P3 (defer), with the reasoning recorded so decisions don't get re-litigated.

## Invariants any future work must preserve

The test suite locks in these guarantees — several items below are shaped (or rejected)
by them:

- `len(streamer)` is the word count (`tests/test_streamer.py::test_len_is_word_count`).
- `reset()` / re-iteration replays from the top
  (`test_iteration_is_rerunnable`, `test_reset_rewinds`).
- Span round-trip: `source[start:end] == out.text` (`test_words_and_spans_round_trip`).
- Pause/resume act at word boundaries; `stop()` interrupts the inter-word delay
  immediately (see `CLAUDE.md`, Testing notes).

## Performance

### [P2] Regex tokenizer — ✅ done 2026-07-05

`WordStreamer._tokenize` (`rsvp_streamer/streamer.py`) hand-rolled a per-character loop.
Now `re.finditer(r"\S+", source)` (`_WORD_RE`) yields the same `(word, start, end)`
triples at C speed with less code. Existing tokenizer tests passed unchanged.

### [P3] Span-only token table

`_tokenize` stores a duplicated word substring alongside each span. Storing only
`(start, end)` and slicing in `step()` roughly halves token-table memory.

- **Honest note:** negligible at typical RSVP input sizes (sentences/paragraphs); only
  matters for very large sources. Anything lazier than this is rejected — it would break
  the `__len__`/`reset()` invariants above.
- **Effort:** low. **Value:** memory only, large inputs.

## Features — reading quality

### [P1] Variable per-word dwell time — ✅ done 2026-07-05, extended 2026-07-07

Every word used to get the flat `streamer.interval`. `StreamPlayer` (and
`WordStreamer.play`) now accept an opt-in `delay_for(out, base_interval) -> float`
strategy returning the per-word dwell in seconds (default: the flat interval);
`base_interval` is re-read each word so runtime rate changes still apply. `stop()`
interrupts custom dwells just like the flat interval; a `delay_for` exception aborts
playback like an `on_word` error.

Extended (2026-07-07) with a built-in preset and break awareness:
- `rsvp_streamer/cadence.py` — `Cadence`, a frozen callable `delay_for` driven by a dict
  of `multipliers` (word's last char, `"long"`, `"line"`, `"paragraph"`) applied
  multiplicatively to the base interval; overrides merge over `DEFAULT_MULTIPLIERS`.
- `StreamOutput.trailing` — the whitespace after each word, so line (`\n`) and paragraph
  (`\n\n`) breaks (dropped by whitespace tokenisation) are visible to a pacer.

Deterministic tests in `tests/test_player.py`; `Cadence` unit tests in
`tests/test_cadence.py`; `trailing` capture in `tests/test_streamer.py`.

### [P2] Punctuation-aware ORP — ✅ done 2026-07-05

Punctuation used to count toward the pivot length, so `hello` pivoted at index 1 but
`hello,` at index 2 — the pinned column jittered. `_identify_center`
(`rsvp_streamer/streamer.py`) now computes the pivot on the trimmed alphanumeric core
(falling back to the raw word when there is no core, e.g. `"—"`), while `text`,
`char_len`, and `center_index` keep referring to the full token. The old
`test_orp_counts_trailing_punctuation` was replaced by punctuation-aware tests.

### [P3] Richer ORP model

Replace the coarse length-based pivot table (`_ORP_THRESHOLDS`) with a
letter-weighted or linguistic model. Research-y; defer until the simpler ORP fix above
has landed and proven insufficient.

## Features — API / UX

### [P2] Playback progress — ✅ done 2026-07-05

`StreamPlayer` now exposes `words_played` (words emitted so far, counting the one
currently in `on_word`) and `progress` (fraction `0.0`–`1.0`; an empty stream reports
`1.0`). Both reset on `start()`, so restarts count afresh.

### [P3] Runtime rate-change convenience

Changing `streamer.rate` mid-playback *already works* — the worker re-reads
`streamer.interval` before each inter-word delay. Optionally add a discoverable
`StreamPlayer.set_rate(wpm)` wrapper and document the existing behavior.

- **Effort:** tiny.

## Deliberately out of scope

### File / iterable / file-object source

Evaluated and dropped (2026-07-05). Streaming from a file only pays off for very large
or non-string (stdin/network) sources, and a naive implementation breaks the
`len()`-is-word-count, `reset()`/re-iteration, and span round-trip guarantees the test
suite locks in. RSVP inputs are sentence-to-article scale, where a single in-memory
`str` is simpler and strictly more capable.

Revisit only with a concrete large-input or streamed-input use case — and then as an
opt-in lazy constructor (e.g. `WordStreamer.from_stream(...)`) that tokenizes across
chunk boundaries, is forward-only (no `len()`/`reset()`), and leaves the in-memory
`str` API and its guarantees untouched.

## Priority summary

| Priority | Item | Status |
| -------- | ---- | ------ |
| **P1** | Variable per-word dwell time | ✅ done 2026-07-05 |
| **P2** | Punctuation-aware ORP · regex tokenizer · playback progress | ✅ done 2026-07-05 |
| **P3** | Span-only token table · richer ORP model · rate-change convenience | deferred |
| Out of scope | File streaming | — |
