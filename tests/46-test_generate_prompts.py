from testwriter.generate import extract_code
from testwriter.prompts import (PROMPT_VERSION, render_baseline,
                                render_initial, render_iteration)


def test_extract_fenced():
    raw = "Here you go:\n```python\ndef test_a():\n    assert True\n```\nThanks!"
    res = extract_code(raw)
    assert res.code and "def test_a" in res.code


def test_extract_unfenced():
    res = extract_code("def test_a():\n    assert True\n")
    assert res.code


def test_extract_rejects_broken():
    res = extract_code("```python\ndef broken(:\n```")
    assert res.code is None and "parse" in res.error


def test_prompts_carry_context():
    p = render_initial("m", "def f():\n    return 1", "import m")
    assert "def f():" in p and "import m" in p and PROMPT_VERSION
    it = render_iteration("m", "src", "import m", [3, 4, 5], "old tests")
    assert "3, 4, 5" in it and "old tests" in it
    b = render_baseline("m", "src", "import m")
    assert "Write tests" in b
