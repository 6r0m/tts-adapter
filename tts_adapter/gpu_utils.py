"""GPU lifecycle utilities shared across TTS engines."""

import gc


def unload_gpu_model(model_ref) -> None:
    """Release a model reference and reclaim CUDA memory.

    Caller is responsible for clearing its own attribute (e.g. `self._model = None`)
    before invoking — this helper only handles gc + CUDA cache flush.
    """
    del model_ref
    gc.collect()

    try:
        import torch
    except ImportError:
        return

    if torch.cuda.is_available():
        torch.cuda.empty_cache()
