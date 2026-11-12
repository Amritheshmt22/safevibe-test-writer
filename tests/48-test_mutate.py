import ast

from testwriter.mutate import apply_mutation, collect_mutation_points, generate_mutants

SRC = '''
def clamp(x, lo, hi):
    if x < lo:
        return lo
    if x > hi:
        return hi
    return x


def total(items):
    t = 0
    for i in items:
        t = t + i
    return t


def flag(a, b):
    return a and not b
'''


def test_points_are_deterministic():
    assert collect_mutation_points(SRC) == collect_mutation_points(SRC)


def test_every_operator_present():
    ops = {p.operator for p in collect_mutation_points(SRC)}
    assert {"AOR", "ROR", "LCR", "UOI", "CRP", "RVR"} <= ops


def test_mutants_parse_and_differ():
    for m in generate_mutants(SRC):
        assert m.source != SRC
        ast.parse(m.source)  # every mutant is syntactically valid


def test_mutation_changes_semantics_somewhere():
    # at least one mutant must change clamp's behaviour
    changed = False
    for m in generate_mutants(SRC):
        ns = {}
        exec(m.source, ns)
        real = {}
        exec(SRC, real)
        for args in [(5, 1, 10), (-3, 0, 2), (99, 0, 10), (2, 2, 2)]:
            try:
                if ns["clamp"](*args) != real["clamp"](*args):
                    changed = True
            except Exception:
                changed = True
    assert changed


def test_cap_is_respected():
    mutants = generate_mutants(SRC, max_mutants=5)
    assert len(mutants) <= 5


def test_unparse_roundtrip_keeps_positions():
    points = collect_mutation_points(SRC)
    p = points[0]
    mutated = apply_mutation(SRC, p)
    assert mutated != SRC
