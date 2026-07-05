import pytest

from word_streamer import StreamError, StreamOutput, WordStreamer


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


def test_orp_counts_trailing_punctuation():
    # Documents the known simplification: punctuation counts toward word
    # length, so "text." (len 5) pivots at 1 like any 5-character word.
    out = WordStreamer(source="text.").step()
    assert out.center_index == 1
    assert out.char_len == 5


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
