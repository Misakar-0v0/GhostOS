from __future__ import annotations

import sys
from typing import Callable, Any
from uuid import uuid4
from contextlib import redirect_stdout
import io


# --- private methods --- #
def __uuid() -> str:
    return str(uuid4())


# --- facade --- #

uuid: Callable[[], str] = __uuid


def dict_without_none(data: dict) -> dict:
    """
    Removes None values from a dictionary.
    """
    result = {}
    for key, value in data.items():
        if value is not None:
            result[key] = value
    return result


def dict_without_zero(data: dict) -> dict:
    """
    Removes zero values from a dictionary.
    """
    result = {}
    for key, value in data.items():
        if not value:
            result[key] = value
    return result


def camel_to_snake(name: str) -> str:
    buffer = ""
    result = ""
    for c in name:
        if 'A' <= c <= 'Z':
            buffer += c
            continue
        buffer_len = len(buffer)
        if buffer_len == 0:
            result += c
        elif buffer_len == 1:
            prefix = '_' if result else ''
            result += prefix + buffer.lower() + c
            buffer = ""
        else:
            prefix = '_' if result else ''
            result += prefix + buffer[:buffer_len - 1].lower() + '_' + buffer[buffer_len - 1] + c
            buffer = ""

    if len(buffer) > 0:
        prefix = '_' if result else ''
        result += prefix + buffer.lower()
    return result


class BufferPrint:
    """
    print 方法的替代.
    """

    def __init__(self):
        self._buffer = io.StringIO()

    def print(self, *args, **kwargs):
        with self._buffer as buffer, redirect_stdout(buffer):
            print(*args, **kwargs)

    def buffer(self) -> str:
        return self._buffer.getvalue()


def import_from_str(module_spec: str) -> Any:
    parts = module_spec.split(':', 2)
    module = parts[0]
    spec = parts[1] if len(parts) > 1 else None
    from importlib import import_module
    imported_module = import_module(module)
    if spec:
        if spec in imported_module:
            return getattr(imported_module, spec)
        raise ModuleNotFoundError(f"No spec named {spec} in module {module}")
    return imported_module
