import pytest

from core.formula import Formula, FormulaError


@pytest.mark.parametrize("text,data,expected", [
    ("((A*256)+B)/4", [0x1A, 0xF8], 1726.0),
    ("A-40", [0x5A], 50),
    ("A*100/255", [255], 100.0),
    ("((A*65536)+(B*256)+C)*0.1", [0x01, 0x86, 0xA0], 10000.0),
    ("((signed(A)*256)+B)/16", [0xFF, 0xF0], -1.0),
    ("signed16((A<<8)|B)", [0x80, 0x00], -32768),
    ("max(A,B)", [3, 9], 9),
])
def test_eval(text, data, expected):
    assert Formula(text)(data) == pytest.approx(expected)


def test_nbytes():
    assert Formula("((A*256)+B)/4").nbytes == 2
    assert Formula("C*2").nbytes == 3
    assert Formula("42").nbytes == 0


@pytest.mark.parametrize("text", [
    "__import__('os').system('x')", "A.real", "open('f')", "[A]", "A if B else C",
    "AB", "a", "A**2", "lambda: 1", "A; B", "'x'", "eval('1')", "min(A, key=B)",
])
def test_rejects_unsafe(text):
    with pytest.raises(FormulaError):
        Formula(text)


def test_short_data():
    with pytest.raises(FormulaError):
        Formula("A*256+B")([1])


def test_named_formula():
    f = Formula("map_wide - baro", names={"map_wide", "baro", "rpm"})
    assert f.vars == {"map_wide", "baro"}
    assert f({"map_wide": 150.0, "baro": 99.0, "rpm": 700}) == 51.0
    with pytest.raises(FormulaError):
        f({"map_wide": 150.0})


def test_named_formula_rejects_unknown_and_letters():
    with pytest.raises(FormulaError):
        Formula("map_wide - nope", names={"map_wide"})
    with pytest.raises(FormulaError):
        Formula("A - B", names={"map_wide"})
