"""Regression checks for the static web UI templates."""

from tts_adapter.web.templates_body import INDEX_BODY
from tts_adapter.web.templates_i18n import TRANSLATIONS
from tts_adapter.web.templates_script import INDEX_SCRIPT


def test_clone_tab_renders_emotion_controls_hidden_by_default():
    assert 'id="emotion-controls"' in INDEX_BODY
    assert 'hidden aria-hidden="true"' in INDEX_BODY
    assert 'id="clone-emotion-mode"' in INDEX_BODY
    assert 'id="clone-emotion-audio"' in INDEX_BODY
    assert 'id="clone-emotion-text"' in INDEX_BODY
    assert 'id="clone-emotion-alpha"' in INDEX_BODY

    for key in ("happy", "angry", "sad", "afraid", "disgusted", "melancholic", "surprised", "calm"):
        assert f'id="clone-emotion-{key}"' in INDEX_BODY


def test_web_script_wires_emotion_controls_and_health_polling():
    assert "supports_emotional_cloning" in INDEX_SCRIPT
    assert "setInterval(() => checkStatus(), HEALTH_POLL_MS)" in INDEX_SCRIPT
    assert "updateEmotionControls(data)" in INDEX_SCRIPT
    assert "appendEmotionFormData(form)" in INDEX_SCRIPT
    assert "form.append('emotion_audio'" in INDEX_SCRIPT
    assert "form.append('emotion_text'" in INDEX_SCRIPT
    assert "form.append('emotion_vector'" in INDEX_SCRIPT
    assert "form.append('emotion_alpha'" in INDEX_SCRIPT


def test_web_i18n_keys_match_between_languages():
    assert set(TRANSLATIONS["ru"]) == set(TRANSLATIONS["en"])
