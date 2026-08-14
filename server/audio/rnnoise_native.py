"""Direct ctypes binding to the official RNNoise C library.

Loads librnnoise from the installed ``pyrnnoise`` wheel without importing
``pyrnnoise.__init__`` (which pulls optional audiolab dependencies).
"""

from __future__ import annotations

import ctypes
import platform
import sys
from pathlib import Path
from typing import Tuple

import numpy as np

SAMPLE_RATE = 48000
DTYPE = np.int16

_lib: ctypes.CDLL | None = None
FRAME_SIZE: int = 480


def _library_names() -> tuple[str, ...]:
    system = platform.system()
    if system == "Darwin":
        return ("librnnoise.dylib",)
    if system == "Windows":
        return ("rnnoise.dll",)
    if system == "Linux":
        return ("librnnoise.so",)
    return ()


def _locate_rnnoise_library() -> Path | None:
    """Find prebuilt RNNoise shared library shipped inside pyrnnoise wheels."""
    names = _library_names()
    if not names:
        return None
    for base in sys.path:
        if not base:
            continue
        pkg_dir = Path(base) / "pyrnnoise"
        if not pkg_dir.is_dir():
            continue
        for name in names:
            candidate = pkg_dir / name
            if candidate.is_file():
                return candidate
    return None


def library_available() -> bool:
    return _locate_rnnoise_library() is not None


def _load_library() -> ctypes.CDLL:
    global _lib, FRAME_SIZE
    if _lib is not None:
        return _lib

    lib_path = _locate_rnnoise_library()
    if lib_path is None:
        raise OSError("RNNoise native library not found (install pyrnnoise wheel)")

    lib = ctypes.CDLL(str(lib_path))
    lib.rnnoise_create.argtypes = [ctypes.c_void_p]
    lib.rnnoise_create.restype = ctypes.c_void_p
    lib.rnnoise_destroy.argtypes = [ctypes.c_void_p]
    lib.rnnoise_process_frame.argtypes = [
        ctypes.c_void_p,
        ctypes.POINTER(ctypes.c_float),
        ctypes.POINTER(ctypes.c_float),
    ]
    lib.rnnoise_process_frame.restype = ctypes.c_float
    lib.rnnoise_get_frame_size.restype = ctypes.c_int

    FRAME_SIZE = int(lib.rnnoise_get_frame_size())
    _lib = lib
    return lib


def create() -> ctypes.c_void_p:
    """Create one RNNoise denoising state (call once per session)."""
    lib = _load_library()
    state = lib.rnnoise_create(None)
    if not state:
        raise RuntimeError("rnnoise_create returned NULL")
    return state


def destroy(state: ctypes.c_void_p | None) -> None:
    if state and _lib is not None:
        _lib.rnnoise_destroy(state)


def process_mono_frame(
    state: ctypes.c_void_p, frame: np.ndarray
) -> Tuple[np.ndarray, float]:
    """Process one RNNoise frame. Input/output int16 mono, length FRAME_SIZE."""
    lib = _load_library()

    if frame.dtype in (np.float32, np.float64):
        pcm = np.clip(frame * 32767.0, -32768, 32767).astype(DTYPE)
    else:
        pcm = frame.astype(DTYPE)

    if len(pcm) < FRAME_SIZE:
        pcm = np.pad(pcm, (0, FRAME_SIZE - len(pcm)))
    elif len(pcm) > FRAME_SIZE:
        pcm = pcm[:FRAME_SIZE]

    work = pcm.astype(np.float32)
    ptr = work.ctypes.data_as(ctypes.POINTER(ctypes.c_float))
    speech_prob = float(lib.rnnoise_process_frame(state, ptr, ptr))
    return np.clip(work, -32768, 32767).astype(DTYPE), speech_prob
