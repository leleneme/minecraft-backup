import os
import tempfile


def get_lock_filename() -> str:
    return os.path.join(tempfile.gettempdir(), 'mcbackup.lock')


def exists() -> bool:
    return os.path.exists(get_lock_filename())


def create():
    filepath = get_lock_filename()
    with open(filepath, 'a'):
        os.utime(filepath)


def delete():
    filepath = get_lock_filename()
    if exists():
        os.remove(filepath)
