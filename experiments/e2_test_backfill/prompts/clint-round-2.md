Module under test: `clint`

```python
# -*- coding: utf-8 -*-

"""
clint.arguments
~~~~~~~~~~~~~~~

This module provides the CLI argument interface.

"""


from __future__ import absolute_import

import os
from sys import argv

try:
    from collections import OrderedDict
except ImportError:
    from .packages.ordereddict import OrderedDict

from .utils import expand_path, is_collection

__all__ = ('Args', )


class Args(object):
    """CLI Argument management."""

    def __init__(self, args=None, no_argv=False):
        if not args:
            if not no_argv:
                self._args = argv[1:]
            else:
                self._args = []
        else:
            self._args = args


    def __len__(self):
        return len(self._args)


    def __repr__(self):
        return '<args %s>' % (repr(self._args))


    def __getitem__(self, i):
        try:
            return self.all[i]
        except IndexError:
            return None


    def __contains__(self, x):
        return self.first(x) is not None


    def get(self, x):
        """Returns argument at given index, else none."""
        try:
            return self.all[x]
        except IndexError:
            return None


    def get_with(self, x):
        """Returns first argument that contains given string."""
        return self.all[self.first_with(x)]


    def remove(self, x):
        """Removes given arg (or list thereof) from Args object."""

        def _remove(x):
            found = self.first(x)
            if found is not None:
                self._args.pop(found)

        if is_collection(x):
            for item in x:
                _remove(x)
        else:
            _remove(x)


    def pop(self, x):
        """Removes and Returns value at given index, else none."""
        try:
            return self._args.pop(x)
        except IndexError:
            return None


    def any_contain(self, x):
        """Tests if given string is contained in any stored argument."""

        return bool(self.first_with(x))


    def contains(self, x):
        """Tests if given object is in arguments list.
           Accepts strings and lists of strings."""

        return self.__contains__(x)


    def first(self, x):
        """Returns first found index of given value (or list of values)"""

        def _find( x):
            try:
                return self.all.index(str(x))
            except ValueError:
                return None

        if is_collection(x):
            for item in x:
                found = _find(item)
                if found is not None:
                    return found
            return None
        else:
            return _find(x)


    def first_with(self, x):
        """Returns first found index containing value (or list of values)"""

        def _find(x):
            try:
                for arg in self.all:
                    if x in arg:
                        return self.all.index(arg)
            except ValueError:
                return None

        if is_collection(x):
            for item in x:
                found = _find(item)
                if found:
                    return found
            return None
        else:
            return _find(x)


    def first_without(self, x):
        """Returns first found index not containing value (or list of values)"""

        def _find(x):
            try:
                for arg in self.all:
                    if x not in arg:
                        return self.all.index(arg)
            except ValueError:
                return None

        if is_collection(x):
            for item in x:
                found = _find(item)
                if found:
                    return found
            return None
        else:
            return _find(x)


    def start_with(self, x):
           """Returns all arguments beginning with given string (or list thereof)"""

           _args = []

           for arg in self.all:
               if is_collection(x):
                   for _x in x:
                       if arg.startswith(x):
                           _args.append(arg)
                           break
               else:
                   if arg.startswith(x):
                       _args.append(arg)

           return Args(_args, no_argv=True)


    def contains_at(self, x, index):
        """Tests if given [list of] string is at given index."""

        try:
            if is_collection(x):
                for _x in x:
                    if (_x in self.all[index]) or (_x == self.all[index]):
                        return True
                    else:
                        return False
            else:
                return (x in self.all[index])

        except IndexError:
            return False


    def has(self, x):
        """Returns true if argument exists at given index.
           Accepts: integer.
        """

        try:
            self.all[x]
            return True
        except IndexError:
            return False


    def value_after(self, x):
        """Returns value of argument after given found argument (or list thereof)."""

        try:
            try:
                i = self.all.index(x)
            except ValueError:
                return None

            return self.all[i + 1]

        except IndexError:
            return None


    @property
    def grouped(self):
        """Extracts --flag groups from argument list.
           Returns {format: Args, ...}
        """

        collection = OrderedDict(_=Args(no_argv=True))

        _current_group = None

        for arg in self.all:
            if arg.startswith('-'):
                _current_group = arg
                collection.setdefault(arg, Args(no_argv=True))
            else:
                if _current_group:
                    collection[_current_group]._args.append(arg)
                else:
                    collection['_']._args.append(arg)

        return collection


    @property
    def last(self):
        """Returns last argument."""

        try:
            return self.all[-1]
        except IndexError:
            return None


    @property
    def all(self):
        """Returns all arguments."""

        return self._args


    def all_with(self, x):
        """Returns all arguments containing given string (or list thereof)"""

        _args = []

        for arg in self.all:
            if is_collection(x):
                for _x in x:
                    if _x in arg:
                        _args.append(arg)
                        break
            else:
                if x in arg:
                    _args.append(arg)

        return Args(_args, no_argv=True)


    def all_without(self, x):
        """Returns all arguments not containing given string (or list thereof)"""

        _args = []

        for arg in self.all:
            if is_collection(x):
                for _x in x:
                    if _x not in arg:
                        _args.append(arg)
                        break
            else:
                if x not in arg:
                    _args.append(arg)

        return Args(_args, no_argv=True)


    @property
    def flags(self):
        """Returns Arg object including only flagged arguments."""

        return self.start_with('-')


    @property
    def not_flags(self):
        """Returns Arg object excluding flagged arguments."""

        return self.all_without('-')


    @property
    def files(self, absolute=False):
        """Returns an expanded list of all valid paths that were passed in."""

        _paths = []

        for arg in self.all:
            for path in expand_path(arg):
                if os.path.exists(path):
                    if absolute:
                        _paths.append(os.path.abspath(path))
                    else:
                        _paths.append(path)

        return _paths


    @property
    def not_files(self):
        """Returns a list of all arguments that aren't files/globs."""

        _args = []

        for arg in self.all:
            if not len(expand_path(arg)):
                if not os.path.exists(arg):
                    _args.append(arg)

        return Args(_args, no_argv=True)

    @property
    def copy(self):
        """Returns a copy of Args object for temporary manipulation."""

        return Args(self.all)


```

The test file below is already accepted. These lines are still NOT
covered: 19, 20, 33, 135, 136, 156, 157, 160, 161, 162, 163, 164, 178, 179, 325, 327, 328, 329, 330, 331, 333, 335, 342, 344, 345, 346, 347, 349.

```python
import pytest

from clint import arguments


def make(*args):
    return arguments.Args(list(args), no_argv=True)


# ---------- construction and basic protocol ----------

def test_init_with_explicit_args():
    a = arguments.Args(['x', 'y'], no_argv=True)
    assert a.all == ['x', 'y']


def test_init_no_argv_empty():
    a = arguments.Args(no_argv=True)
    assert a.all == []


def test_len():
    assert len(make('a', 'b', 'c')) == 3


def test_len_empty():
    assert len(make()) == 0


def test_repr():
    assert repr(make('a')) == "<args ['a']>"


def test_getitem_returns_arg():
    assert make('a', 'b')[1] == 'b'


def test_getitem_out_of_range_returns_none():
    assert make('a')[5] is None


# ---------- get / get_with ----------

def test_get_returns_item():
    assert make('a', 'b').get(0) == 'a'


def test_get_missing_returns_none():
    assert make('a').get(9) is None


def test_get_with_finds_containing_arg():
    a = make('--output=file.txt', 'x')
    assert a.get_with('output') == '--output=file.txt'


def test_get_with_missing_raises_typeerror():
    # self.all[None] is invalid indexing: the code raises TypeError
    with pytest.raises(TypeError):
        make('a', 'b').get_with('zzz')


# ---------- first / first_with / first_without ----------

def test_first_scalar_found():
    assert make('a', 'b', 'c').first('b') == 1


def test_first_scalar_missing():
    assert make('a', 'b').first('z') is None


def test_first_list_returns_first_matching_index():
    # list items are tried in order: 'c' is found at index 2 and returned
    assert make('a', 'b', 'c').first(['c', 'a']) == 2


def test_first_list_all_missing():
    assert make('a').first(['x', 'y']) is None


def test_first_with_scalar():
    assert make('--foo', 'bar').first_with('foo') == 0


def test_first_with_scalar_missing():
    assert make('bar').first_with('foo') is None


def test_first_with_list_misses_index_zero_quirk():
    # the list branch checks `if found:` so a match at index 0 is lost
    a = make('--foo', 'bar')
    assert a.first_with(['--f']) is None


def test_first_with_list_matches_later_index():
    a = make('bar', '--foo')
    assert a.first_with(['--f']) == 1


def test_first_without_scalar():
    assert make('--a', 'plain', 'other').first_without('-') == 1


def test_first_without_all_contain():
    assert make('-a', '-b').first_without('-') is None


# ---------- contains / any_contain / contains_at ----------

def test_contains_true():
    assert make('a', 'b').contains('b') is True


def test_contains_false():
    assert make('a', 'b').contains('z') is False


def test_dunder_contains():
    assert 'a' in make('a', 'b')


def test_any_contain_true():
    assert make('plain', '--output=x').any_contain('output') is True


def test_any_contain_index_zero_quirk():
    # bool(first_with(x)) is False when the only match sits at index 0
    assert make('--output=x').any_contain('output') is False


def test_any_contain_false():
    assert make('plain').any_contain('output') is False


def test_contains_at_match():
    assert make('abc', 'def').contains_at('bc', 0) is True


def test_contains_at_no_match():
    assert make('abc', 'def').contains_at('zz', 0) is False


def test_contains_at_out_of_range():
    assert make('a').contains_at('a', 7) is False


def test_contains_at_list_first_item_decides():
    # only the first list item is examined: it returns after it
    a = make('abc')
    assert a.contains_at(['bc', 'zz'], 0) is True
    assert a.contains_at(['zz', 'bc'], 0) is False


# ---------- has / pop / remove / value_after / last ----------

def test_has_valid_index():
    assert make('a', 'b').has(1) is True


def test_has_invalid_index():
    assert make('a').has(4) is False


def test_pop_returns_and_removes():
    a = make('a', 'b', 'c')
    assert a.pop(1) == 'b'
    assert a.all == ['a', 'c']


def test_pop_missing_returns_none():
    assert make('a').pop(9) is None


def test_remove_scalar():
    a = make('a', 'b', 'c')
    a.remove('b')
    assert a.all == ['a', 'c']


def test_remove_missing_is_noop():
    a = make('a')
    a.remove('zzz')
    assert a.all == ['a']


def test_remove_list_removes_matches():
    a = make('a', 'b', 'c')
    a.remove(['a', 'b'])
    assert a.all == ['c']


def test_value_after_returns_next():
    assert make('--mode', 'fast', 'x').value_after('--mode') == 'fast'


def test_value_after_last_returns_none():
    assert make('a', '--flag').value_after('--flag') is None


def test_value_after_missing_returns_none():
    assert make('a').value_after('zzz') is None


def test_last_property():
    assert make('a', 'b').last == 'b'


def test_last_empty_returns_none():
    assert make().last is None


# ---------- grouped / flags / not_flags ----------

def test_grouped_separates_flags_and_values():
    a = make('--opt1', 'val1', 'val2', '--opt2', 'val3')
    groups = a.grouped
    assert groups['--opt1'].all == ['val1', 'val2']
    assert groups['--opt2'].all == ['val3']
    assert groups['_'].all == []


def test_grouped_leading_plain_args_go_to_default_group():
    a = make('file.txt', '--verbose')
    groups = a.grouped
    assert groups['_'].all == ['file.txt']
    assert groups['--verbose'].all == []


def test_flags_property():
    a = make('--verbose', 'file.txt', '--debug')
    assert a.flags.all == ['--verbose', '--debug']


def test_not_flags_property():
    a = make('--verbose', 'file.txt')
    assert a.not_flags.all == ['file.txt']


def test_not_flags_excludes_args_containing_dash_anywhere():
    # all_without('-') drops any arg containing '-', not just prefixes
    a = make('has-dash', 'plain')
    assert a.not_flags.all == ['plain']


def test_start_with_scalar():
    a = make('--foo', 'bar', '--fizz')
    assert a.start_with('--').all == ['--foo', '--fizz']


def test_start_with_list_raises_typeerror_quirk():
    # the collection branch passes the whole list to str.startswith
    with pytest.raises(TypeError):
        make('--foo').start_with(['-', 'x'])


# ---------- all_with / all_without ----------

def test_all_with_scalar():
    a = make('--out=a', 'plain', '--output=b')
    assert a.all_with('out').all == ['--out=a', '--output=b']


def test_all_with_list_any_match():
    a = make('alpha', 'beta', 'gamma')
    assert a.all_with(['alph', 'amm']).all == ['alpha', 'gamma']


def test_all_without_scalar():
    a = make('keep', 'drop-me')
    assert a.all_without('drop').all == ['keep']


def test_all_without_list():
    a = make('alpha', 'beta', 'gamma')
    assert a.all_without(['alph', 'eta']).all == ['gamma']


# ---------- copy ----------

def test_copy_returns_args_instance():
    a = make('x', 'y')
    b = a.copy
    assert isinstance(b, arguments.Args)
    assert b.all == ['x', 'y']


def test_copy_shares_list_reference_quirk():
    # copy wraps the same underlying list (Args(self.all))
    a = make('x')
    b = a.copy
    assert b.all is a.all
```

Write a NEW pytest test file containing ONLY additional tests that cover
the missing lines and any related edge cases. Do not repeat existing
tests. Import the module as `from clint import arguments`.
