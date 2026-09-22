"""Lexer: logical lines, comments, indentation and tokens (SPEC §2)."""

from __future__ import annotations

import pytest
from conftest import codes, compile_wod, lex, token_texts, tokens_of

from wodcraft.syntax.lexer import Line, strip_comment


# --------------------------------------------------------------------------- comments


def test_double_slash_starts_a_comment():
    # Arrange / Act
    code, comment = strip_comment("For time // the main block")

    # Assert
    assert code == "For time "
    assert comment == "the main block"


def test_url_inside_a_comment_survives():
    # Arrange
    text = "// see https://example.com/wods?a=1"

    # Act
    code, comment = strip_comment(text)

    # Assert — the '//' of the URL must not cut the comment short
    assert code == ""
    assert comment == "see https://example.com/wods?a=1"


def test_url_in_a_quoted_string_is_not_a_comment():
    # Arrange / Act
    code, comment = strip_comment('10 Burpee ("https://example.com")')

    # Assert
    assert comment is None
    assert code == '10 Burpee ("https://example.com")'


def test_slashes_glued_to_a_word_do_not_start_a_comment():
    # A dual such as 20/16 or a path must survive; '//' only opens a comment
    # at the start of a line or after whitespace.
    code, comment = strip_comment("20/16 cal Row")
    assert comment is None
    assert code == "20/16 cal Row"


def test_comment_only_line_keeps_its_text_and_number():
    # Arrange / Act
    lines, bag = lex("# A\n  // a note\nFor time\n")

    # Assert
    note = next(line for line in lines if line.comment == "a note")
    assert note.number == 2
    assert note.text == ""
    assert bag.items == []


def test_blank_and_whitespace_only_lines_are_dropped():
    lines, _ = lex("For time\n\n   \n  10 Burpee\n")
    assert [line.number for line in lines] == [1, 4]


# --------------------------------------------------------------------------- indentation


def test_tab_in_indentation_is_e002_with_its_column():
    # Arrange
    source = "For time\n  10 Burpee\n\t10 Air squat\n"

    # Act
    lines, bag = lex(source)

    # Assert
    assert [(d.code, d.span.line, d.span.col) for d in bag.items] == [("E002", 3, 1)]
    # the tab is replaced by two spaces so the rest of the file still parses
    assert lines[-1].indent == 2


def test_tab_after_spaces_reports_its_own_column():
    _, bag = lex("For time\n  \t10 Burpee\n")
    diagnostic = bag.items[0]
    assert (diagnostic.code, diagnostic.span.line, diagnostic.span.col) == ("E002", 2, 3)


def test_tab_inside_the_text_is_not_an_indentation_error():
    _, bag = lex("For time\n  10\tBurpee\n")
    assert bag.items == []


def test_indent_is_measured_in_spaces():
    lines, _ = lex("For time\n    10 Burpee\n")
    assert [line.indent for line in lines] == [0, 4]
    assert lines[1].col0 == 5


def test_crlf_and_cr_line_endings_are_normalised():
    lines, _ = lex("For time\r\n  10 Burpee\r\n")
    assert [line.text for line in lines] == ["For time", "10 Burpee"]
    assert [line.number for line in lines] == [1, 2]


# --------------------------------------------------------------------------- numbers


def test_decimal_comma_is_e003_and_suggests_the_dot():
    # Arrange
    source = "For time\n  10 Thruster 43,5 kg\n"

    # Act
    result = compile_wod(source)

    # Assert
    assert codes(result) == ["E003"]
    diagnostic = result.diagnostics[0]
    assert (diagnostic.span.line, diagnostic.span.col, diagnostic.span.end_col) == (2, 15, 19)
    assert diagnostic.suggestion == "write '43.5'"


def test_decimal_comma_still_produces_the_corrected_number():
    # after E003 the lexer keeps going with the dotted value
    tokens = tokens_of("43,5 kg")
    assert [(t.kind, t.text) for t in tokens] == [("NUM", "43.5"), ("WORD", "kg")]


def test_decimal_point_is_accepted():
    assert token_texts("1.5 pood") == ["1.5", "pood"]


# --------------------------------------------------------------------------- tokens


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("400m", [("NUM", "400"), ("WORD", "m")]),
        ("400 m", [("NUM", "400"), ("WORD", "m")]),
        ("20/16", [("NUM", "20"), ("SYM", "/"), ("NUM", "16")]),
        ("1:30", [("CLOCK", "1:30")]),
        ("1:00:00", [("CLOCK", "1:00:00")]),
        ("5x5", [("SETS", "5x5")]),
        ("5X5", [("SETS", "5x5")]),
        ("5×5", [("SETS", "5x5")]),
        ("->", [("ARROW", "->")]),
        ("→", [("ARROW", "→")]),
        ("...", [("ELLIPSIS", "...")]),
        ("…", [("ELLIPSIS", "…")]),
        ('"strict"', [("STRING", '"strict"')]),
        ("@ 75%", [("SYM", "@"), ("NUM", "75"), ("SYM", "%")]),
        ("21-15-9", [("NUM", "21"), ("SYM", "-"), ("NUM", "15"), ("SYM", "-"), ("NUM", "9")]),
    ],
)
def test_token_kinds(text, expected):
    assert [(t.kind, t.text) for t in tokens_of(text)] == expected


def test_hyphenated_words_are_one_token():
    assert token_texts("Pull-up") == ["Pull-up"]
    assert token_texts("Chest-to-bar pull-up") == ["Chest-to-bar", "pull-up"]


def test_glued_flag_distinguishes_400m_from_400_m():
    glued = tokens_of("400m")
    spaced = tokens_of("400 m")
    assert [t.glued for t in glued] == [False, True]
    assert [t.glued for t in spaced] == [False, False]


def test_token_columns_account_for_indentation():
    tokens = tokens_of("21 Thruster", indent=4)
    assert [(t.text, t.col, t.end_col) for t in tokens] == [("21", 5, 7), ("Thruster", 8, 16)]


def test_unexpected_character_is_e001_at_its_column():
    result = compile_wod("AMRAP 10:00\n  10 Burpee $\n")
    diagnostic = result.diagnostics[0]
    assert diagnostic.code == "E001"
    assert (diagnostic.span.line, diagnostic.span.col) == (2, 13)
    assert "'$'" in diagnostic.message


def test_string_token_keeps_its_quotes_and_inner_spaces():
    (token,) = tokens_of('"chest to the floor"')
    assert token.kind == "STRING"
    assert token.text == '"chest to the floor"'


def test_is_word_is_case_insensitive():
    (token,) = tokens_of("AMRAP")
    assert token.is_word("amrap") is True
    assert token.lower == "amrap"
    assert token.is_word("emom") is False


def test_is_sym():
    tokens = tokens_of("@")
    assert tokens[0].is_sym("@") is True
    assert tokens[0].is_sym("/") is False


def test_sets_token_requires_no_trailing_digit_or_dot():
    # "5x5" is a set scheme; "1.5" must not be mistaken for one
    assert [t.kind for t in tokens_of("1.5")] == ["NUM"]


def test_line_dataclass_defaults():
    line = Line(7, 2, "10 Burpee", "  10 Burpee")
    assert line.comment is None
    assert line.col0 == 3
