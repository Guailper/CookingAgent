"""Tests for local voice transcription configuration defaults."""

import os
import unittest

from src.core.config import _get_voice_provider_default, get_settings


class VoiceLocalConfigTests(unittest.TestCase):
    """Keep local faster-whisper selection predictable across env combinations."""

    def setUp(self) -> None:
        self._original_env = os.environ.copy()
        get_settings.cache_clear()

    def tearDown(self) -> None:
        os.environ.clear()
        os.environ.update(self._original_env)
        get_settings.cache_clear()

    def test_local_model_env_switches_default_provider_to_local(self) -> None:
        os.environ.pop("VOICE_TRANSCRIBE_PROVIDER", None)
        os.environ.pop("VOICE_TRANSCRIBE_BASE_URL", None)
        os.environ.pop("VOICE_TRANSCRIBE_API_KEY", None)
        os.environ["VOICE_LOCAL_MODEL"] = "small"

        self.assertEqual(_get_voice_provider_default(), "local_faster_whisper")

    def test_settings_include_local_faster_whisper_defaults(self) -> None:
        os.environ["VOICE_TRANSCRIBE_PROVIDER"] = "local_faster_whisper"
        os.environ["VOICE_LOCAL_MODEL"] = "small"
        os.environ.pop("VOICE_LOCAL_DEVICE", None)
        os.environ.pop("VOICE_LOCAL_COMPUTE_TYPE", None)
        os.environ.pop("VOICE_LOCAL_VAD_FILTER", None)

        settings = get_settings()

        self.assertEqual(settings.voice_transcribe_provider, "local_faster_whisper")
        self.assertEqual(settings.voice_local_model, "small")
        self.assertEqual(settings.voice_local_device, "auto")
        self.assertEqual(settings.voice_local_compute_type, "int8")
        self.assertTrue(settings.voice_local_vad_filter)


if __name__ == "__main__":
    unittest.main()
