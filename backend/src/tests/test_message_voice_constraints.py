"""Regression tests for the text-only voice input flow."""

import unittest

from pydantic import ValidationError

from src.core.constants import INPUT_SOURCE_KEYBOARD, INPUT_SOURCE_VOICE, MESSAGE_TYPE_TEXT
from src.schemas.message import CreateMessageRequest
from src.services.message_service import MessageService


class CreateMessageRequestTests(unittest.TestCase):
    """Validate the public API contract for text-only user messages."""

    def test_accepts_voice_input_source_for_text_messages(self) -> None:
        payload = CreateMessageRequest(
            content="把这段语音转成文字后发出去",
            message_type=MESSAGE_TYPE_TEXT,
            extra_metadata={"input_source": INPUT_SOURCE_VOICE},
        )

        self.assertEqual(payload.message_type, MESSAGE_TYPE_TEXT)
        self.assertIsNotNone(payload.extra_metadata)
        self.assertEqual(payload.extra_metadata.input_source, INPUT_SOURCE_VOICE)

    def test_rejects_non_text_message_type(self) -> None:
        with self.assertRaises(ValidationError):
            CreateMessageRequest(content="hello", message_type="audio")

    def test_rejects_unknown_input_source(self) -> None:
        with self.assertRaises(ValidationError):
            CreateMessageRequest(content="hello", extra_metadata={"input_source": "call"})


class MessageServiceMetadataNormalizationTests(unittest.TestCase):
    """Keep message metadata aligned with the transcription-only product scope."""

    def test_defaults_to_keyboard_when_metadata_is_missing(self) -> None:
        normalized = MessageService._normalize_user_message_metadata(None)

        self.assertEqual(normalized, {"input_source": INPUT_SOURCE_KEYBOARD})

    def test_keeps_voice_source_and_other_fields(self) -> None:
        normalized = MessageService._normalize_user_message_metadata(
            {
                "input_source": INPUT_SOURCE_VOICE,
                "transcript_duration_ms": 8120,
            }
        )

        self.assertEqual(normalized["input_source"], INPUT_SOURCE_VOICE)
        self.assertEqual(normalized["transcript_duration_ms"], 8120)


if __name__ == "__main__":
    unittest.main()
