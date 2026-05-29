"""Tests for attachment upload transaction cleanup."""

import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace

from src.services.file_service import FileService


class _FakeDb:
    def __init__(self) -> None:
        self.rolled_back = False

    def rollback(self) -> None:
        self.rolled_back = True


class _FailingAttachmentRepository:
    def create(self, attachment):
        _ = attachment
        raise RuntimeError("database insert failed")


class _ConversationRepository:
    def get_by_public_id_and_user_id(self, public_id, user_id):
        _ = (public_id, user_id)
        return SimpleNamespace(id=10)


class FileServiceUploadTests(unittest.IsolatedAsyncioTestCase):
    async def test_upload_cleans_current_file_when_attachment_insert_fails(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            stored_path = Path(temp_dir) / "new-upload.pdf"
            service = FileService.__new__(FileService)
            service.db = _FakeDb()
            service.settings = SimpleNamespace(max_message_attachments=5)
            service.attachment_repository = _FailingAttachmentRepository()
            service.conversation_repository = _ConversationRepository()

            async def build_attachment(conversation_id, upload):
                _ = (conversation_id, upload)
                stored_path.write_bytes(b"written before database flush")
                return SimpleNamespace(), stored_path

            service._build_attachment = build_attachment

            with self.assertRaises(RuntimeError):
                await service.upload_conversation_attachments(
                    user=SimpleNamespace(id=1),
                    conversation_public_id="conv_test",
                    files=[object()],
                )

            self.assertTrue(service.db.rolled_back)
            self.assertFalse(stored_path.exists())


if __name__ == "__main__":
    unittest.main()
