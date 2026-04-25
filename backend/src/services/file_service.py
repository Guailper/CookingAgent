"""Attachment upload and cleanup workflows for chat conversations."""

import hashlib
from pathlib import Path
from typing import Any

from fastapi import UploadFile
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from src.core.config import get_settings
from src.core.constants import (
    ALLOWED_DOCUMENT_EXTENSIONS,
    ALLOWED_IMAGE_EXTENSIONS,
    ATTACHMENT_KIND_DOCUMENT,
    ATTACHMENT_KIND_IMAGE,
    ATTACHMENT_STORAGE_LOCAL,
    PARSE_STATUS_PENDING,
)
from src.core.exceptions import AppException
from src.core.security import generate_public_id
from src.db.models.attachment import Attachment
from src.db.models.user import User
from src.repositories.attachment_repository import AttachmentRepository
from src.repositories.conversation_repository import ConversationRepository


class FileService:
    """Validate, persist, and clean up attachments bound to conversations."""

    def __init__(self, db: Session) -> None:
        self.db = db
        self.settings = get_settings()
        self.attachment_repository = AttachmentRepository(db)
        self.conversation_repository = ConversationRepository(db)

    async def upload_conversation_attachments(
        self,
        user: User,
        conversation_public_id: str,
        files: list[UploadFile],
    ) -> list[Attachment]:
        """Upload one or more files and return unbound attachment records."""

        if not files:
            raise AppException(400, "ATTACHMENT_REQUIRED", "请至少选择一个文件后再上传。")
        if len(files) > self.settings.max_message_attachments:
            raise AppException(
                400,
                "ATTACHMENT_LIMIT_EXCEEDED",
                f"单条消息最多允许上传 {self.settings.max_message_attachments} 个附件。",
            )

        conversation = self.conversation_repository.get_by_public_id_and_user_id(
            conversation_public_id,
            user.id,
        )
        if conversation is None:
            raise AppException(404, "CONVERSATION_NOT_FOUND", "未找到对应会话。")

        created_attachments: list[Attachment] = []
        written_paths: list[Path] = []

        try:
            for upload in files:
                attachment, stored_path = await self._build_attachment(conversation.id, upload)
                self.attachment_repository.create(attachment)
                created_attachments.append(attachment)
                written_paths.append(stored_path)

            self.db.commit()
        except AppException:
            self.db.rollback()
            self._cleanup_paths(written_paths)
            raise
        except IntegrityError as exc:
            self.db.rollback()
            self._cleanup_paths(written_paths)
            raise AppException(409, "ATTACHMENT_CREATE_CONFLICT", "附件上传时发生冲突。") from exc
        except Exception:
            self.db.rollback()
            self._cleanup_paths(written_paths)
            raise

        for attachment in created_attachments:
            self.db.refresh(attachment)

        return created_attachments

    def delete_unbound_attachment(self, user: User, attachment_public_id: str) -> None:
        """Delete an uploaded attachment only when it is still unbound."""

        attachment = self.attachment_repository.get_by_public_id(attachment_public_id)
        if attachment is None:
            raise AppException(404, "ATTACHMENT_NOT_FOUND", "未找到对应附件。")

        conversation = self.conversation_repository.get_by_id(attachment.conversation_id)
        if conversation is None or conversation.user_id != user.id:
            raise AppException(404, "ATTACHMENT_NOT_FOUND", "未找到对应附件。")
        if attachment.message_id is not None:
            raise AppException(
                409,
                "ATTACHMENT_ALREADY_BOUND",
                "该附件已经绑定到正式消息，无法再删除。",
            )

        stored_path = self.settings.upload_dir_path / attachment.storage_path

        try:
            self.attachment_repository.delete(attachment)
            self.db.commit()
        except Exception:
            self.db.rollback()
            raise

        self._cleanup_paths([stored_path])

    async def _build_attachment(self, conversation_id: int, upload: UploadFile) -> tuple[Attachment, Path]:
        """Validate a single upload, write it to disk, and build its ORM record."""

        original_name = Path(upload.filename or "attachment").name
        file_ext = Path(original_name).suffix.lower()
        if not file_ext:
            raise AppException(400, "UNSUPPORTED_FILE_TYPE", "当前文件缺少扩展名，无法识别类型。")

        attachment_kind = self._resolve_attachment_kind(file_ext)
        file_bytes = await upload.read()
        if not file_bytes:
            raise AppException(400, "EMPTY_FILE", "当前文件内容为空，无法上传。")

        max_size_bytes = self.settings.max_upload_size_mb * 1024 * 1024
        if len(file_bytes) > max_size_bytes:
            raise AppException(
                400,
                "FILE_TOO_LARGE",
                f"当前文件超过 {self.settings.max_upload_size_mb}MB 限制。",
            )

        stored_name = f"{generate_public_id('attfile')}{file_ext}"
        conversation_dir = self.settings.upload_dir_path / "conversations" / str(conversation_id)
        conversation_dir.mkdir(parents=True, exist_ok=True)
        target_path = conversation_dir / stored_name
        target_path.write_bytes(file_bytes)

        attachment = Attachment(
            public_id=generate_public_id("att"),
            conversation_id=conversation_id,
            message_id=None,
            original_name=original_name,
            stored_name=stored_name,
            file_ext=file_ext,
            mime_type=upload.content_type or "application/octet-stream",
            file_size=len(file_bytes),
            attachment_kind=attachment_kind,
            storage_provider=ATTACHMENT_STORAGE_LOCAL,
            storage_path=str(target_path.relative_to(self.settings.upload_dir_path)),
            file_hash=hashlib.sha256(file_bytes).hexdigest(),
            parse_status=PARSE_STATUS_PENDING,
        )

        return attachment, target_path

    def _resolve_attachment_kind(self, file_ext: str) -> str:
        """Map extensions into the two attachment kinds supported by the composer."""

        if file_ext in ALLOWED_IMAGE_EXTENSIONS:
            return ATTACHMENT_KIND_IMAGE
        if file_ext in ALLOWED_DOCUMENT_EXTENSIONS:
            return ATTACHMENT_KIND_DOCUMENT

        raise AppException(
            400,
            "UNSUPPORTED_FILE_TYPE",
            "当前仅支持 PDF、Office 文档、TXT、以及常见图片格式。",
        )

    def _cleanup_paths(self, paths: list[Path]) -> None:
        """Best-effort cleanup for files written before a transaction failed."""

        for path in paths:
            try:
                path.unlink(missing_ok=True)
            except OSError:
                # File cleanup should never hide the original application error.
                continue
