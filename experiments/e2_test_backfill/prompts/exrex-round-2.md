Module under test: `exrex`

```python
#!/usr/bin/env python
# -*- coding: utf-8 -*-

# This file is part of exrex.
#
# exrex is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# exrex is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU Affero General Public License for more details.
#
# You should have received a copy of the GNU Affero General Public License
# along with exrex. If not, see < http://www.gnu.org/licenses/ >.
#
# (C) 2012- by Adam Tauber, <asciimoo@gmail.com>

try:
    from future_builtins import map, range
except:
    pass
from re import match, U
try:
    import re._parser as sre_parse
except ImportError: # Python < 3.11
    from re import sre_parse
from itertools import tee
from random import choice, randint
from types import GeneratorType

from sys import version_info
IS_PY3 = version_info[0] == 3
IS_PY36_OR_GREATER = IS_PY3 and version_info[1] > 5

if IS_PY3:
    unichr = chr

__all__ = (
    'generate',
    'CATEGORIES',
    'count',
    'parse',
    'getone',
    'sre_to_string',
    'simplify'
)

CATEGORIES = {
    sre_parse.CATEGORY_SPACE: sorted(sre_parse.WHITESPACE),
    sre_parse.CATEGORY_NOT_SPACE: [unichr(x) for x in range(256) if
                                   match(r'\S', unichr(x), U)],
    sre_parse.CATEGORY_DIGIT: sorted(sre_parse.DIGITS),
    sre_parse.CATEGORY_NOT_DIGIT: [unichr(x) for x in range(256) if
                                   match(r'\D', unichr(x), U)],
    sre_parse.CATEGORY_WORD: [unichr(x) for x in range(256) if
                              match(r'\w', unichr(x), U)],
    sre_parse.CATEGORY_NOT_WORD: [unichr(x) for x in range(256) if
                                  match(r'\W', unichr(x), U)],
    'category_any': [unichr(x) for x in range(32, 123)]
}


def _build_reverse_categories():
    reverse = {}
    for key, value in sre_parse.CATEGORIES.items():
        if not hasattr(value[1], '__iter__'):
            continue

        for vv in value[1]:
            if value[0] == sre_parse.IN and vv[0] == sre_parse.CATEGORY:
                reverse.update({vv[1]: key})

    return reverse


REVERSE_CATEGORIES = _build_reverse_categories()


def comb(g, i):
    for c in g:
        g2, i = tee(i)
        for c2 in g2:
            yield c + c2


def mappend(g, c):
    for cc in g:
        yield cc + c


def dappend(g, d, k):
    for cc in g:
        yield cc + d[k]


def _in(d):
    ret = []
    neg = False
    for i in d:
        if i[0] == sre_parse.RANGE:
            subs = map(unichr, range(i[1][0], i[1][1] + 1))
            if neg:
                for char in subs:
                    try:
                        ret.remove(char)
                    except:
                        pass
            else:
                ret.extend(subs)
        elif i[0] == sre_parse.LITERAL:
            if neg:
                try:
                    ret.remove(unichr(i[1]))
                except:
                    pass
            else:
                ret.append(unichr(i[1]))
        elif i[0] == sre_parse.CATEGORY:
            subs = CATEGORIES.get(i[1], [''])
            if neg:
                for char in subs:
                    try:
                        ret.remove(char)
                    except:
                        pass
            else:
                ret.extend(subs)
        elif i[0] == sre_parse.NEGATE:
            ret = list(CATEGORIES['category_any'])
            neg = True
    return ret


def prods(orig, ran, items, limit, grouprefs):
    for o in orig:
        for r in ran:
            if r == 0:
                yield o
            else:
                ret = [o]
                for _ in range(r):
                    ret = ggen(
                        ret, _gen, items, limit=limit, count=False, grouprefs=grouprefs)
                for i in ret:
                    yield i


def ggen(g1, f, *args, **kwargs):
    groupref = None
    grouprefs = kwargs.get('grouprefs', {})
    if 'groupref' in kwargs.keys():
        groupref = kwargs.pop('groupref')
    for a in g1:
        g2 = f(*args, **kwargs)
        if isinstance(g2, GeneratorType):
            for b in g2:
                grouprefs[groupref] = b
                yield a + b
        else:
            yield g2


def concit(g1, seqs, limit, grouprefs):
    for a in g1:
        for s in seqs:
            for b in _gen(s, limit, grouprefs=grouprefs):
                yield a + b


def _gen(d, limit=20, count=False, grouprefs=None):
    """docstring for _gen"""
    if grouprefs is None:
        grouprefs = {}
    ret = ['']
    strings = 0
    literal = False
    for i in d:
        if i[0] == sre_parse.IN:
            subs = _in(i[1])
            if count:
                strings = (strings or 1) * len(subs)
            ret = comb(ret, subs)
        elif i[0] == sre_parse.LITERAL:
            literal = True
            ret = mappend(ret, unichr(i[1]))
        elif i[0] == sre_parse.CATEGORY:
            subs = CATEGORIES.get(i[1], [''])
            if count:
                strings = (strings or 1) * len(subs)
            ret = comb(ret, subs)
        elif i[0] == sre_parse.ANY:
            subs = CATEGORIES['category_any']
            if count:
                strings = (strings or 1) * len(subs)
            ret = comb(ret, subs)
        elif i[0] == sre_parse.MAX_REPEAT or i[0] == sre_parse.MIN_REPEAT:
            items = list(i[1][2])
            if i[1][1] + 1 - i[1][0] >= limit:
                r1 = i[1][0]
                r2 = i[1][0] + limit
            else:
                r1 = i[1][0]
                r2 = i[1][1] + 1
            ran = range(r1, r2)
            if count:
                branch_count = 0
                for p in ran:
                    branch_count += pow(_gen(items, limit, True, grouprefs), p)
                strings = (strings or 1) * branch_count

            ret = prods(ret, ran, items, limit, grouprefs)
        elif i[0] == sre_parse.BRANCH:
            if count:
                branch_count = 0
                for x in i[1][1]:
                    branch_count += _gen(x, limit, True, grouprefs) or 1
                strings = (strings or 1) * branch_count
            ret = concit(ret, i[1][1], limit, grouprefs)
        elif i[0] == sre_parse.SUBPATTERN or i[0] == sre_parse.ASSERT:
            subexpr = i[1][1]
            if IS_PY36_OR_GREATER and i[0] == sre_parse.SUBPATTERN:
                subexpr = i[1][3]
            if count:
                strings = (
                    strings or 1) * (sum(ggen([0], _gen, subexpr, limit=limit, count=True, grouprefs=grouprefs)) or 1)
            ret = ggen(ret, _gen, subexpr, limit=limit, count=False, grouprefs=grouprefs, groupref=i[1][0])
        # ignore ^ and $
        elif i[0] == sre_parse.AT:
            continue
        elif i[0] == sre_parse.NOT_LITERAL:
            subs = list(CATEGORIES['category_any'])
            if unichr(i[1]) in subs:
                subs.remove(unichr(i[1]))
            if count:
                strings = (strings or 1) * len(subs)
            ret = comb(ret, subs)
        elif i[0] == sre_parse.GROUPREF:
            ret = dappend(ret, grouprefs, i[1])
        elif i[0] == sre_parse.ASSERT_NOT:
            pass
        else:
            print('[!] cannot handle expression ' + repr(i))

    if count:
        if strings == 0 and literal:
            inc = True
            for i in d:
                if i[0] not in (sre_parse.AT, sre_parse.LITERAL):
                    inc = False
            if inc:
                strings = 1
        return strings

    return ret


def _randone(d, limit=20, grouprefs=None):
    if grouprefs is None:
        grouprefs = {}
    """docstring for _randone"""
    ret = ''
    for i in d:
        if i[0] == sre_parse.IN:
            ret += choice(_in(i[1]))
        elif i[0] == sre_parse.LITERAL:
            ret += unichr(i[1])
        elif i[0] == sre_parse.CATEGORY:
            ret += choice(CATEGORIES.get(i[1], ['']))
        elif i[0] == sre_parse.ANY:
            ret += choice(CATEGORIES['category_any'])
        elif i[0] == sre_parse.MAX_REPEAT or i[0] == sre_parse.MIN_REPEAT:
            if i[1][1] + 1 - i[1][0] >= limit:
                min, max = i[1][0], i[1][0] + limit - 1
            else:
                min, max = i[1][0], i[1][1]
            for _ in range(randint(min, max)):
                ret += _randone(list(i[1][2]), limit, grouprefs)
        elif i[0] == sre_parse.BRANCH:
            ret += _randone(choice(i[1][1]), limit, grouprefs)
        elif i[0] == sre_parse.SUBPATTERN or i[0] == sre_parse.ASSERT:
            subexpr = i[1][1]
            if IS_PY36_OR_GREATER and i[0] == sre_parse.SUBPATTERN:
                subexpr = i[1][3]
            subp = _randone(subexpr, limit, grouprefs)
            if i[1][0]:
                grouprefs[i[1][0]] = subp
            ret += subp
        elif i[0] == sre_parse.AT:
            continue
        elif i[0] == sre_parse.NOT_LITERAL:
            c = list(CATEGORIES['category_any'])
            if unichr(i[1]) in c:
                c.remove(unichr(i[1]))
            ret += choice(c)
        elif i[0] == sre_parse.GROUPREF:
            ret += grouprefs[i[1]]
        elif i[0] == sre_parse.ASSERT_NOT:
            pass
        else:
            print('[!] cannot handle expression "%s"' % str(i))

    return ret


def sre_to_string(sre_obj, paren=True):
    """sre_parse object to string

    :param sre_obj: Output of sre_parse.parse()
    :type sre_obj: list
    :rtype: str
    """
    ret = u''
    for i in sre_obj:
        if i[0] == sre_parse.IN:
            prefix = ''
            if len(i[1]) and i[1][0][0] == sre_parse.NEGATE:
                prefix = '^'
            ret += u'[{0}{1}]'.format(prefix, sre_to_string(i[1], paren=paren))
        elif i[0] == sre_parse.LITERAL:
            u = unichr(i[1])
            ret += u if u not in sre_parse.SPECIAL_CHARS else '\\{0}'.format(u)
        elif i[0] == sre_parse.CATEGORY:
            ret += REVERSE_CATEGORIES[i[1]]
        elif i[0] == sre_parse.ANY:
            ret += '.'
        elif i[0] == sre_parse.BRANCH:
            # TODO simplifications here
            parts = [sre_to_string(x, paren=paren) for x in i[1][1]]
            if not any(parts):
                continue
            if i[1][0]:
                if len(parts) == 1:
                    paren = False
                prefix = ''
            else:
                prefix = '?:'
            branch = '|'.join(parts)
            if paren:
                ret += '({0}{1})'.format(prefix, branch)
            else:
                ret += '{0}'.format(branch)
        elif i[0] == sre_parse.SUBPATTERN:
            subexpr = i[1][1]
            if IS_PY36_OR_GREATER and i[0] == sre_parse.SUBPATTERN:
                subexpr = i[1][3]
            if i[1][0]:
                ret += '({0})'.format(sre_to_string(subexpr, paren=False))
            else:
                ret += '{0}'.format(sre_to_string(subexpr, paren=paren))
        elif i[0] == sre_parse.NOT_LITERAL:
            ret += '[^{0}]'.format(unichr(i[1]))
        elif i[0] == sre_parse.MAX_REPEAT:
            if i[1][0] == i[1][1]:
                range_str = '{{{0}}}'.format(i[1][0])
            else:
                if i[1][0] == 0 and i[1][1] - i[1][0] == sre_parse.MAXREPEAT:
                    range_str = '*'
                elif i[1][0] == 1 and i[1][1] - i[1][0] == sre_parse.MAXREPEAT - 1:
                    range_str = '+'
                else:
                    range_str = '{{{0},{1}}}'.format(i[1][0], i[1][1])
            ret += sre_to_string(i[1][2], paren=paren) + range_str
        elif i[0] == sre_parse.MIN_REPEAT:
            if i[1][0] == 0 and i[1][1] == sre_parse.MAXREPEAT:
                range_str = '*?'
            elif i[1][0] == 1 and i[1][1] == sre_parse.MAXREPEAT:
                range_str = '+?'
            elif i[1][1] == sre_parse.MAXREPEAT:
                range_str = '{{{0},}}?'.format(i[1][0])
            else:
                range_str = '{{{0},{1}}}?'.format(i[1][0], i[1][1])
            ret += sre_to_string(i[1][2], paren=paren) + range_str
        elif i[0] == sre_parse.GROUPREF:
            ret += '\\{0}'.format(i[1])
        elif i[0] == sre_parse.AT:
            if i[1] == sre_parse.AT_BEGINNING:
                ret += '^'
            elif i[1] == sre_parse.AT_END:
                ret += '$'
        elif i[0] == sre_parse.NEGATE:
            pass
        elif i[0] == sre_parse.RANGE:
            ret += '{0}-{1}'.format(unichr(i[1][0]), unichr(i[1][1]))
        elif i[0] == sre_parse.ASSERT:
            if i[1][0]:
                ret += '(?={0})'.format(sre_to_string(i[1][1], paren=False))
            else:
                ret += '{0}'.format(sre_to_string(i[1][1], paren=paren))
        elif i[0] == sre_parse.ASSERT_NOT:
            pass
        else:
            print('[!] cannot handle expression "%s"' % str(i))
    return ret


def simplify(regex_string):
    """Simplify a regular expression

    :param regex_string: Regular expression
    :type regex_string: str
    :rtype: str
    """
    r = parse(regex_string)
    return sre_to_string(r)


def parse(s):
    """Regular expression parser

    :param s: Regular expression
    :type s: str
    :rtype: list
    """
    if IS_PY3:
        r = sre_parse.parse(s, flags=U)
    else:
        r = sre_parse.parse(s.decode('utf-8'), flags=U)
    return list(r)


def generate(s, limit=20):
    """Creates a generator that generates all matching strings to a given regular expression

    :param s: Regular expression
    :type s: str
    :param limit: Range limit
    :type limit: int
    :returns: string generator object
    """
    return _gen(parse(s), limit)


def count(s, limit=20):
    """Counts all matching strings to a given regular expression

    :param s: Regular expression
    :type s: str
    :param limit: Range limit
    :type limit: int
    :rtype: int
    :returns: number of matching strings
    """
    return _gen(parse(s), limit, count=True)


def getone(regex_string, limit=20):
    """Returns a random matching string to a given regular expression
    """
    return _randone(parse(regex_string), limit)


def argparser():
    import argparse
    from sys import stdout
    argp = argparse.ArgumentParser(
        description='exrex - regular expression string generator')
    argp.add_argument(
        '-o', '--output',
        help='Output file - default is STDOUT',
        metavar='FILE',
        default=stdout,
        type=argparse.FileType('w', encoding='utf-8')
    )
    argp.add_argument(
        '-l', '--limit',
        help='Max limit for range size - default is 20',
        default=20,
        action='store',
        type=int,
        metavar='N'
    )
    argp.add_argument(
        '-c', '--count',
        help='Count matching strings',
        default=False,
        action='store_true'
    )
    argp.add_argument(
        '-m', '--max-number',
        help='Max number of strings - default is -1',
        default=-1,
        action='store',
        type=int,
        metavar='N'
    )
    argp.add_argument(
        '-r', '--random',
        help='Returns a random string that matches to the regex',
        default=False,
        action='store_true'
    )
    argp.add_argument(
        '-s', '--simplify',
        help='Simplifies a regular expression',
        default=False,
        action='store_true'
    )
    argp.add_argument(
        '-d', '--delimiter',
        help='Delimiter - default is \\n',
        default='\n'
    )
    argp.add_argument(
        '-v', '--verbose',
        action='store_true',
        help='Verbose mode',
        default=False
    )
    argp.add_argument(
        'regex',
        metavar='REGEX',
        help='REGEX string'
    )
    return vars(argp.parse_args())


def __main__():
    from sys import exit, stderr
    args = argparser()
    if args['verbose']:
        args['output'].write(
            '%r%s' % (parse(args['regex']), args['delimiter']))
    if args['count']:
        args['output'].write(
            '%d%s' % (count(args['regex'], limit=args['limit']), args['delimiter']))
        exit(0)
    if args['random']:
        args['output'].write(
            '%s%s' % (getone(args['regex'], limit=args['limit']), args['delimiter']))
        exit(0)
    if args['simplify']:
        args['output'].write(
            '%s%s' % (simplify(args['regex']), args['delimiter']))
        exit(0)
    try:
        g = generate(args['regex'], args['limit'])
    except Exception as e:
        stderr.write('[!] Error: %s\n' % e)
        exit(1)
    args['output'].write(next(g))
    args['max_number'] -= 1
    for s in g:
        if args['max_number'] == 0:
            break
        args['max_number'] -= 1
        args['output'].write(args['delimiter'])
        args['output'].write(s)
    if args['delimiter'] == '\n':
        args['output'].write('\n')


if __name__ == '__main__':
    __main__()

```

The test file below is already accepted. These lines are still NOT
covered: 95, 96, 106, 107, 108, 109, 110, 115, 116, 117, 118, 124, 125, 126, 127, 128, 131, 132, 133, 163, 190, 191, 192, 193, 195, 196, 197, 198, 227, 240, 241, 242, 243, 245, 252, 271, 273, 276, 283, 284, 285, 286, 287, 288, 289, 290, 291, 292, 293, 294, 295, 296, 297, 298, 299, 300, 301, 303, 320, 326, 328, 331, 332, 333, 334, 335, 336, 337, 339, 340, 341, 342, 344, 346, 347, 348, 349, 350, 352, 354.

```python
import re

import exrex


# ---------- generate(): exhaustive string enumeration ----------

def test_generate_single_literal():
    assert list(exrex.generate('a')) == ['a']


def test_generate_multiple_literals():
    assert list(exrex.generate('abc')) == ['abc']


def test_generate_character_class():
    assert sorted(exrex.generate('[ab]')) == ['a', 'b']


def test_generate_concatenation_of_classes():
    assert sorted(exrex.generate('[ab][12]')) == ['a1', 'a2', 'b1', 'b2']


def test_generate_branch():
    assert sorted(exrex.generate('cat|dog')) == ['cat', 'dog']


def test_generate_optional_group():
    assert sorted(exrex.generate('colou?r')) == ['color', 'colour']


def test_generate_group_branch_with_suffix():
    assert sorted(exrex.generate('(a|b)c')) == ['ac', 'bc']


def test_generate_anchors_are_ignored():
    assert list(exrex.generate('^ab$')) == ['ab']


def test_generate_repeat_range():
    assert sorted(exrex.generate('a{2,3}')) == ['aa', 'aaa']


def test_generate_digit_category_matches_digits_only():
    result = list(exrex.generate('[0-9]'))
    assert result == [str(d) for d in range(10)]


def test_generate_star_with_limit():
    # 'a*' with limit=3 yields '', 'a', 'aa' (repeat counts 0..2)
    assert sorted(exrex.generate('a*', limit=3)) == ['', 'a', 'aa']


# ---------- count(): size of the generated language ----------

def test_count_single_literal():
    assert exrex.count('a') == 1


def test_count_literal_string():
    assert exrex.count('abc') == 1


def test_count_character_class():
    assert exrex.count('[ab]') == 2


def test_count_range_class():
    assert exrex.count('[0-9]') == 10


def test_count_two_digit_range():
    assert exrex.count('[0-9]{2}') == 100


def test_count_branch():
    assert exrex.count('cat|dog') == 2


def test_count_optional():
    assert exrex.count('colou?r') == 2


def test_count_repeat_range():
    assert exrex.count('a{2,3}') == 2


def test_count_digit_category():
    assert exrex.count('\\d') == 10


def test_count_matches_generate_length():
    pattern = '[ab][12]'
    assert exrex.count(pattern) == len(list(exrex.generate(pattern)))


def test_count_negated_class():
    # category_any holds characters 32..122 (91 chars); removing 'a' leaves 90
    assert exrex.count('[^a]') == 90


# ---------- getone(): random matching string ----------

def test_getone_literal_is_exact():
    assert exrex.getone('abc') == 'abc'


def test_getone_matches_pattern():
    for _ in range(25):
        s = exrex.getone('[ab]{3}')
        assert re.fullmatch(r'[ab]{3}', s)


def test_getone_repeat_matches_pattern():
    for _ in range(25):
        s = exrex.getone('x[0-9]{2}y')
        assert re.fullmatch(r'x[0-9]{2}y', s)


def test_getone_branch_matches_one_alternative():
    for _ in range(25):
        assert exrex.getone('cat|dog') in ('cat', 'dog')


# ---------- simplify(): regex -> canonical regex ----------

def test_simplify_star():
    assert exrex.simplify('a*') == 'a*'


def test_simplify_plus():
    assert exrex.simplify('a+') == 'a+'


def test_simplify_exact_repeat():
    assert exrex.simplify('a{3}') == 'a{3}'


def test_simplify_character_range():
    assert exrex.simplify('[a-c]') == '[a-c]'


def test_simplify_preserves_semantics():
    # a simplified regex must accept exactly what the original accepts
    original = 'colou?r'
    simplified = exrex.simplify(original)
    for text in ('color', 'colour'):
        assert re.fullmatch(simplified, text)
    assert not re.fullmatch(simplified, 'colr')


def test_simplify_anchors():
    assert exrex.simplify('^ab$') == '^ab$'


# ---------- parse(): regex -> token list ----------

def test_parse_returns_list():
    result = exrex.parse('ab')
    assert isinstance(result, list)


def test_parse_literal_tokens_present():
    result = exrex.parse('ab')
    assert len(result) == 2  # two literal tokens
```

Write a NEW pytest test file containing ONLY additional tests that cover
the missing lines and any related edge cases. Do not repeat existing
tests. Import the module as `import exrex`.
