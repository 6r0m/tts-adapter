"""TTS Engine protocol - the universal interface for all TTS backends."""

from typing import Any, Protocol, runtime_checkable

from .contract import GenerationParam, ModelInfo


@runtime_checkable
class TTSEngine(Protocol):
    """Universal TTS engine interface.

    All engine implementations must satisfy this protocol.
    """

    def warmup(self) -> None:
        """Load model into memory and prepare for inference.

        Called once at startup. Should handle model download if needed.
        """
        ...

    def synthesize(
        self,
        text: str,
        language: str = "Auto",
        speaker: str = "default",
        instruct: str = "",
        **kwargs: Any,
    ) -> bytes:
        """Generate WAV audio bytes from text.

        Args:
            text: Text to synthesize
            language: Language code or 'Auto' for auto-detection
            speaker: Speaker/voice identifier
            instruct: Style instruction (tone, emotion, pace)

        Returns:
            WAV audio bytes
        """
        ...

    def synthesize_batch(
        self,
        texts: list[str],
        language: str = "Auto",
        speaker: str = "default",
        instruct: str = "",
        **kwargs: Any,
    ) -> list[bytes]:
        """Batch generation - multiple prompts in one forward pass.

        Args:
            texts: List of texts to synthesize
            language: Language code (same for all)
            speaker: Speaker/voice identifier (same for all)
            instruct: Style instruction (same for all)

        Returns:
            List of WAV audio bytes, one per input text
        """
        ...

    @property
    def engine_name(self) -> str:
        """Return engine identifier (e.g., 'qwen3')."""
        ...

    @property
    def model_id(self) -> str:
        """Return loaded model identifier."""
        ...

    @property
    def device(self) -> str:
        """Return device string (e.g., 'cuda:0', 'cpu')."""
        ...

    @property
    def supports_cloning(self) -> bool:
        """Whether this engine/model supports voice cloning."""
        ...

    @property
    def supports_design(self) -> bool:
        """Whether this engine/model supports voice design from description."""
        ...

    @property
    def supports_custom_voice(self) -> bool:
        """Whether this engine/model supports preset speakers (Simple TTS)."""
        ...

    @property
    def supports_emotional_cloning(self) -> bool:
        """Whether this engine can combine voice cloning with emotion control.

        Convenience flag derived from `emotion_modes`. True iff the engine
        supports at least one emotion input mode. Routes still enforce
        per-mode rejection via `emotion_modes` so a "text-only" engine
        rejects `emotion_audio` even though `supports_emotional_cloning=True`.
        """
        ...

    @property
    def emotion_modes(self) -> set[str]:
        """Which emotion input modes this engine accepts.

        Subset of {"audio", "text", "vector"}. Empty set = no emotion
        support. Routes reject per-mode with 400 if the requested mode
        isn't in this set, so a single-mode engine like VoxCPM2 ({"text"})
        rejects emotion_audio without silently dropping it.
        """
        ...

    @property
    def supports_emotion_strength(self) -> bool:
        """Whether emotion_alpha (intensity in [0.0, 1.0]) is meaningful.

        IndexTTS2 has emo_alpha; VoxCPM2 does not (only cfg_value, which
        isn't a clean intensity knob). Routes 400-reject non-default
        emotion_alpha when this is False, so users don't think they're
        controlling intensity when they're not.
        """
        ...

    @property
    def supports_cyrillic_text(self) -> bool:
        """Whether the engine's tokenizer + acoustic model handle Cyrillic.

        IndexTTS2's normalizer routes any non-Latin text to the Chinese
        tokenizer (front.py:use_chinese), garbling Russian/Ukrainian/Bulgarian.
        Routes use this flag to gate the text-script bypass (e.g. someone
        sends `language=English` with Cyrillic body), independent of which
        languages the engine claims to support.

        Cyrillic includes more than Russian - do NOT derive this from
        `"Russian" in supported_languages`.
        """
        ...

    @classmethod
    def is_installed(cls) -> bool:
        """Whether this engine's files are on disk.

        MUST be cheap: filesystem stat only. No imports of heavy libs,
        no GPU touch, no HTTP calls. For remote workers this checks the
        vendor venv + checkpoint dir; for in-process engines it checks
        the importable package + model path.

        Distinct from `is_reachable()` (worker /health responds) and
        `is_loaded` (warmup completed).
        """
        ...

    def is_reachable(self) -> bool:
        """Whether the engine's backend is currently callable.

        For in-process engines this equals `is_installed()`. For remote
        workers this pings /health with a short timeout. Used by /engines
        and /model/switch to surface 503 with a "start the worker" hint
        instead of a confusing 500.
        """
        ...

    @property
    def is_loaded(self) -> bool:
        """Whether the model is currently warmed up in memory."""
        ...

    @property
    def generation_params(self) -> list[GenerationParam]:
        """Tunable generation knobs THIS engine actually accepts.

        Empty list = the engine has no exposed knobs. UI hides the
        Advanced Settings panel entirely for engines that return [].
        Avoids the trap where the panel shows qwen-style temperature/top_k
        for an engine like VoxCPM2 that uses cfg_value/inference_timesteps
        instead - controls would do nothing.
        """
        ...

    @property
    def supported_languages(self) -> list[str]:
        """Languages this engine actually accepts as input.

        Includes "Auto" if the engine has language auto-detection. The API
        layer rejects requests whose `language` is not in this list with 400
        + actionable hint (switch to an engine that supports it). Drives the
        UI dropdown so the site is the source of truth - users only see
        languages that will actually work.

        Engine-specific language NAMES (not BCP-47 codes) - match what the
        engine library expects (e.g. "Russian" not "ru"). Document the
        canonical list in the engine's docs/engines/<name>/README.md.
        """
        ...

    def catalog_models(self) -> list[ModelInfo]:
        """Static, ALWAYS-returned list of models this engine knows about.

        Used by /model/switch to validate the requested ID. Returning a known
        model here even when its backend is currently down is what allows the
        switch endpoint to attempt warmup() and surface a 503 with an
        actionable hint, rather than rejecting the request as 400 unknown.

        For in-process engines (Qwen3) this equals available_models().
        For remote engines (IndexTTS2RemoteEngine) this returns the static
        entry regardless of worker health.
        """
        ...

    def available_models(self) -> list[ModelInfo]:
        """Models this engine can switch to RIGHT NOW.

        Used by /models so the UI dropdown only offers reachable choices.
        Engines whose backend is unreachable return [] - they get filtered
        out of /models without route-level engine-name branching.
        """
        ...

    def synthesize_clone(
        self,
        text: str,
        reference_audio: bytes,
        language: str = "Auto",
        reference_text: str | None = None,
        *,
        emotion_audio: bytes | str | None = None,
        emotion_text: str | None = None,
        emotion_vector: list[float] | None = None,
        emotion_alpha: float = 1.0,
        **kwargs: Any,
    ) -> bytes:
        """Clone voice from reference audio, optionally with emotion control.

        Args:
            text: Text to synthesize
            reference_audio: WAV bytes of reference voice (3-10 sec)
            language: Language code
            reference_text: Optional transcript of reference audio
            emotion_audio: WAV bytes/path for emotion reference
                (engines without supports_emotional_cloning ignore this)
            emotion_text: Free-form emotion description
            emotion_vector: 8-dim vector ordered as
                [happy, angry, sad, afraid, disgusted, melancholic, surprised, calm]
            emotion_alpha: Emotion blend strength in [0.0, 1.0]

        Returns:
            WAV audio bytes

        Raises:
            NotImplementedError: If engine doesn't support cloning
        """
        ...

    def synthesize_design(
        self,
        text: str,
        instruct: str,
        language: str = "Auto",
        **kwargs: Any,
    ) -> bytes:
        """Generate speech with voice designed from description.

        Args:
            text: Text to synthesize
            instruct: Natural language voice description
            language: Language code

        Returns:
            WAV audio bytes

        Raises:
            NotImplementedError: If engine doesn't support voice design
        """
        ...

    def reload(self, model_id: str) -> None:
        """Reload engine with a different model.

        Unloads current model and loads the specified model.

        Args:
            model_id: New model ID to load
        """
        ...
