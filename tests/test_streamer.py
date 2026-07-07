import pytest

from rsvp_streamer import StreamError, StreamOutput, WordStreamer


def test_words_and_spans_round_trip():
    src = "  Rapid serial  visual\npresentation streams text.  "
    outs = list(WordStreamer(source=src))

    assert [o.text for o in outs] == [
        "Rapid", "serial", "visual", "presentation", "streams", "text.",
    ]
    for o in outs:
        start, end = o.indices
        assert src[start:end] == o.text
        assert o.char_len == len(o.text)


@pytest.mark.parametrize("text", ["", "   \n\t "])
def test_blank_source_is_empty_stream(text):
    assert list(WordStreamer(source=text)) == []


def test_trailing_whitespace_is_captured():
    # trailing is the whitespace run up to the next word (or end of source).
    src = "one two\nthree\n\nfour  "
    outs = list(WordStreamer(source=src))
    assert [(o.text, o.trailing) for o in outs] == [
        ("one", " "),
        ("two", "\n"),
        ("three", "\n\n"),
        ("four", "  "),          # trailing whitespace after the final word
    ]


def test_len_is_word_count():
    assert len(WordStreamer(source="one two three")) == 3


@pytest.mark.parametrize(
    "length,expected",
    [(1, 0), (5, 1), (6, 2), (9, 2), (10, 3), (13, 3), (14, 4), (30, 4)],
)
def test_orp_pivot_table(length, expected):
    assert WordStreamer()._identify_center("x" * length) == expected


def test_iteration_is_rerunnable():
    streamer = WordStreamer(source="alpha beta gamma")
    assert [o.text for o in streamer] == [o.text for o in streamer]


def test_step_returns_none_at_end():
    streamer = WordStreamer(source="a b")
    assert streamer.step().text == "a"
    assert streamer.step().text == "b"
    assert streamer.step() is None
    assert streamer.step() is None


def test_reset_rewinds():
    streamer = WordStreamer(source="a b")
    streamer.step()
    streamer.reset()
    assert streamer.step().text == "a"


def test_generate_output_shape():
    out = WordStreamer(source="hello").step()
    assert isinstance(out, StreamOutput)
    assert out == StreamOutput.from_span("hello", 1, 0)


def test_orp_ignores_trailing_punctuation():
    # "hello," is 6 chars, but the pivot comes from the 5-letter core —
    # same ORP as bare "hello", so the pinned column does not jitter.
    # char_len still counts the punctuation.
    out = WordStreamer(source="hello,").step()
    assert out.center_index == 1
    assert out.char_len == 6


def test_orp_skips_leading_punctuation():
    # Core "hello" starts at index 1; its pivot (1) lands at index 2 overall,
    # so the fixated character is still the word's second letter.
    out = WordStreamer(source='"hello').step()
    assert out.center_index == 2
    assert out.text[out.center_index] == "e"


def test_orp_all_punctuation_falls_back_to_raw_word():
    # No alphanumeric core: pivot on the raw length ("..." len 3 -> index 1).
    out = WordStreamer(source="...").step()
    assert out.center_index == 1


@pytest.mark.parametrize("rate,interval", [(300, 0.2), (600, 0.1)])
def test_interval_from_rate(rate, interval):
    assert WordStreamer(rate=rate).interval == pytest.approx(interval)


@pytest.mark.parametrize("bad", [0, -5])
def test_rate_must_be_positive(bad):
    with pytest.raises(StreamError):
        WordStreamer(rate=bad)


def test_source_must_be_str():
    with pytest.raises(StreamError):
        WordStreamer(source=123)


def test_reassigning_source_retokenizes_and_resets():
    streamer = WordStreamer(source="a b c")
    streamer.step()
    streamer.source = "x y"
    assert len(streamer) == 2
    assert streamer.step().text == "x"
