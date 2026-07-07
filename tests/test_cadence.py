import pytest

from rsvp_streamer import DEFAULT_MULTIPLIERS, Cadence, StreamOutput

BASE = 0.2  # a distinctive base interval so scaling is visible


def out(text, trailing=""):
    """A StreamOutput with the fields Cadence reads (len, last char, trailing)."""
    return StreamOutput.from_span(text, 0, 0, trailing)


def test_plain_word_is_unscaled():
    assert Cadence()(out("word"), BASE) == pytest.approx(BASE)


def test_long_word_is_slowed():
    # "presentation" is 12 chars (> default long_word_len of 9).
    assert Cadence()(out("presentation"), BASE) == pytest.approx(BASE * 1.5)


@pytest.mark.parametrize("word,mult", [("end.", 2.0), ("hey!", 2.0), ("what?", 2.0), ("so,", 1.4)])
def test_trailing_punctuation_is_slowed(word, mult):
    assert Cadence()(out(word), BASE) == pytest.approx(BASE * mult)


def test_line_break_is_slowed():
    assert Cadence()(out("word", "\n"), BASE) == pytest.approx(BASE * 1.5)


def test_paragraph_break_is_slowed_more_than_a_line():
    assert Cadence()(out("word", "\n\n"), BASE) == pytest.approx(BASE * 2.5)
    assert Cadence()(out("word", "\n\n\n"), BASE) == pytest.approx(BASE * 2.5)  # 2+ == paragraph


def test_multipliers_compose_multiplicatively():
    # "presentation." ends a paragraph: long (1.5) * sentence (2.0) * paragraph (2.5).
    assert Cadence()(out("presentation.", "\n\n"), BASE) == pytest.approx(BASE * 1.5 * 2.0 * 2.5)


def test_custom_multipliers_merge_over_defaults():
    cad = Cadence(multipliers={"paragraph": 4.0})
    assert cad(out("word", "\n\n"), BASE) == pytest.approx(BASE * 4.0)  # overridden
    assert cad(out("end."), BASE) == pytest.approx(BASE * 2.0)          # default kept
    assert cad.multipliers[","] == DEFAULT_MULTIPLIERS[","]


def test_long_word_len_is_configurable():
    cad = Cadence(long_word_len=3)
    assert cad(out("word"), BASE) == pytest.approx(BASE * 1.5)  # 4 chars now counts as long


def test_is_frozen():
    with pytest.raises(Exception):
        Cadence().long_word_len = 5
