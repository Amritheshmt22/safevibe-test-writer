Module under test: `pox`

```python
#!/usr/bin/env python
#
# Authors: Gael Varoquaux <gael dot varoquaux at normalesup dot org>
#          Lars Buitinck <L.J.Buitinck@uva.nl>
# Copyright (c) 2010 Gael Varoquaux
# License: BSD Style, 3 clauses.

# Forked by: Mike McKerns (December 2013)
# Author: Mike McKerns (mmckerns @caltech and @uqfoundation)
# Copyright (c) 2013-2016 California Institute of Technology.
# Copyright (c) 2016-2026 The Uncertainty Quantification Foundation.
# License: 3-clause BSD.  The full license text is available at:
#  - https://github.com/uqfoundation/pox/blob/master/LICENSE
"""
Disk management utilities.
"""

import os
import shutil
import sys
import time


def disk_used(path):
    """get the disk usage for the given directory

    Args:
        path (str): path string.

    Returns:
        int corresponding to disk usage in blocks.
    """
    size = 0
    for file in os.listdir(path) + ['.']:
        stat = os.stat(os.path.join(path, file))
        if hasattr(stat, 'st_blocks'):
            size += stat.st_blocks * 512
        else:
            # on some platform st_blocks is not available (e.g., Windows)
            # approximate by rounding to next multiple of 512
            size += (stat.st_size // 512 + 1) * 512
    # We need to convert to int to avoid having longs on some systems (we
    # don't want longs to avoid problems we SQLite)
    return int(size / 1024.)


def kbytes(text):
    """convert memory text to the corresponding value in kilobytes

    Args:
        text (str): string corresponding to an abbreviation of size.

    Returns:
        int representation of text.

    Examples:
        >>> kbytes(\'10K\')
        10
        >>> 
        >>> kbytes(\'10G\')
        10485760
    """
    kilo = 1024
    units = dict(K=1, M=kilo, G=kilo ** 2)
    try:
        size = int(units[text[-1]] * float(text[:-1]))
    except (KeyError, ValueError):
        raise ValueError(
                "Invalid literal for size: '%s' should be "
                "a string like '10G', '500M', '50K'" % text
                )
    return size


# if a rmtree operation fails, wait for this much time (in secs),
# then retry once. if it still fails, raise the exception
RM_SUBDIRS_RETRY_TIME = 0.1

def rmtree(path, self=True, ignore_errors=False, onerror=None):
    """remove directories in the given path

    Args:
        path (str): path string of root of directories to delete.
        self (bool, default=True): if False, delete subdirectories, not path.
        ignore_errors (bool, default=False): if True, silently ignore errors.
        onerror (function, default=None): custom error handler.

    Returns:
        None

    Notes:
        If self=False, the directory indicated by path is left in place,
        and its subdirectories are erased. If self=True, path is also removed.

        If ignore_errors=True, errors are ignored. Otherwise, onerror is called
        to handle the error with arguments ``(func, path, exc_info)``, where
        *func* is ``os.listdir``, ``os.remove``, or ``os.rmdir``; *path* is the
        argument to the function that caused it to fail; and *exc_info* is a
        tuple returned by ``sys.exc_info()``. If ignore_errors=False and
        onerror=None, an exception is raised.
    """
    names = []
    try:
        names = os.listdir(path)
    except os.error:
        if onerror is not None:
            onerror(os.listdir, path, sys.exc_info())
        elif ignore_errors:
            return
        else:
            raise
    if self:
        names = ['']

    for name in names:
        fullname = os.path.join(path, name)
        if os.path.isdir(fullname):
            if onerror is not None:
                shutil.rmtree(fullname, ignore_errors, onerror)
            else:
                # allow the rmtree to fail once, wait and re-try.
                # if the error is raised again, fail
                err_count = 0
                while True:
                    try:
                        shutil.rmtree(fullname, ignore_errors, None)
                        break
                    except os.error:
                        if err_count > 0:
                            raise
                        err_count += 1
                        time.sleep(RM_SUBDIRS_RETRY_TIME)


# EOF

```

The test file below is already accepted. These lines are still NOT
covered: 41, 119, 128, 129, 130, 131, 132.

```python
import os

import pytest

from pox import _disk


# ---------- kbytes: text -> kilobyte conversion ----------

def test_kbytes_kilobytes():
    assert _disk.kbytes('10K') == 10


def test_kbytes_megabytes():
    assert _disk.kbytes('500M') == 500 * 1024


def test_kbytes_gigabytes():
    assert _disk.kbytes('10G') == 10 * 1024 * 1024


def test_kbytes_fractional_truncates_to_int():
    # 1.5K = 1536 bytes -> 1 KB after int()
    assert _disk.kbytes('1.5K') == 1


def test_kbytes_two_and_half_megabytes():
    # 2.5M = 2560K exactly
    assert _disk.kbytes('2.5M') == 2560


def test_kbytes_single_kilobyte():
    assert _disk.kbytes('1K') == 1


def test_kbytes_invalid_unit_raises_valueerror():
    with pytest.raises(ValueError):
        _disk.kbytes('10T')


def test_kbytes_no_unit_raises_valueerror():
    with pytest.raises(ValueError):
        _disk.kbytes('10')


def test_kbytes_non_numeric_raises_valueerror():
    with pytest.raises(ValueError):
        _disk.kbytes('abcK')


def test_kbytes_error_message_mentions_literal():
    with pytest.raises(ValueError) as excinfo:
        _disk.kbytes('10T')
    assert '10T' in str(excinfo.value)


# ---------- disk_used: real directory sizes ----------

def test_disk_used_empty_directory(tmp_path):
    used = _disk.disk_used(str(tmp_path))
    assert isinstance(used, int)
    assert used >= 0


def test_disk_used_counts_file_blocks(tmp_path):
    f = tmp_path / 'data.bin'
    f.write_bytes(b'x' * 8192)
    empty = tmp_path / 'empty'
    empty.mkdir()
    assert _disk.disk_used(str(tmp_path)) > _disk.disk_used(str(empty))


def test_disk_used_returns_int_for_file_dir(tmp_path):
    (tmp_path / 'f.txt').write_text('hello')
    used = _disk.disk_used(str(tmp_path))
    assert isinstance(used, int)
    assert used > 0


# ---------- rmtree: recursive removal ----------

def _tree(root):
    (root / 'sub1').mkdir()
    (root / 'sub1' / 'nested').mkdir()
    (root / 'sub1' / 'nested' / 'leaf.txt').write_text('leaf')
    (root / 'sub2').mkdir()
    (root / 'top.txt').write_text('top')


def test_rmtree_self_true_removes_root(tmp_path):
    target = tmp_path / 'victim'
    target.mkdir()
    _tree(target)
    _disk.rmtree(str(target))
    assert not target.exists()


def test_rmtree_self_false_keeps_root_removes_subdirs(tmp_path):
    target = tmp_path / 'victim'
    target.mkdir()
    _tree(target)
    _disk.rmtree(str(target), self=False)
    assert target.exists()
    assert not (target / 'sub1').exists()
    assert not (target / 'sub2').exists()
    # note: with self=False only subdirectories are removed;
    # the top-level file is left in place by this implementation
    assert (target / 'top.txt').exists()


def test_rmtree_ignore_errors_on_missing_path(tmp_path):
    missing = str(tmp_path / 'does-not-exist')
    # must not raise
    _disk.rmtree(missing, ignore_errors=True)


def test_rmtree_missing_path_raises_by_default(tmp_path):
    missing = str(tmp_path / 'does-not-exist')
    with pytest.raises(OSError):
        _disk.rmtree(missing)


def test_rmtree_onerror_handler_called_with_listdir(tmp_path):
    calls = []

    def handler(func, path, exc_info):
        calls.append(func)

    missing = str(tmp_path / 'does-not-exist')
    _disk.rmtree(missing, onerror=handler)
    assert calls == [os.listdir]
```

Write a NEW pytest test file containing ONLY additional tests that cover
the missing lines and any related edge cases. Do not repeat existing
tests. Import the module as `from pox import _disk`.
