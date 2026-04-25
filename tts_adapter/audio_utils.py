"""Audio shape utilities shared across TTS engines.

Pure functions - no engine state, no GPU calls. Engines compose these
helpers instead of duplicating tempfile / silence-trim logic.
"""

import os
import tempfile
from contextlib import contextmanager
from typing import Iterator


def trim_silence(wav, sr: int, pad_seconds: float = 0.05):
    """Trim leading/trailing near-silence to avoid padded output.

    Returns the wav unchanged if numpy is unavailable or the signal is empty.
    Threshold is 1% of peak amplitude with a small padding window so we don't
    cut into actual speech onset/offset.
    """
    try:
        import numpy as np
    except ImportError:
        return wav

    wav_arr = np.asarray(wav)
    if wav_arr.size == 0:
        return wav_arr

    if wav_arr.ndim == 2:
        signal = np.max(np.abs(wav_arr), axis=1)
    else:
        signal = np.abs(wav_arr)

    max_amp = float(signal.max()) if signal.size else 0.0
    if max_amp <= 0:
        return wav_arr

    threshold = max(max_amp * 0.01, 1e-4)
    indices = np.where(signal > threshold)[0]
    if indices.size == 0:
        return wav_arr

    pad = int(sr * pad_seconds)
    start = max(int(indices[0]) - pad, 0)
    end = min(int(indices[-1]) + pad + 1, wav_arr.shape[0])
    return wav_arr[start:end]


@contextmanager
def bytes_to_tempfile(data: bytes, suffix: str = ".wav") -> Iterator[str]:
    """Write bytes to a NamedTemporaryFile, yield its path, unlink on exit.

    Cleanup runs even on exception. Caller receives a filesystem path that
    third-party libraries (e.g. IndexTTS2's `infer(spk_audio_prompt=...)`)
    can open directly.
    """
    fd, path = tempfile.mkstemp(suffix=suffix)
    try:
        with os.fdopen(fd, "wb") as f:
            f.write(data)
        yield path
    finally:
        try:
            os.unlink(path)
        except FileNotFoundError:
            pass
