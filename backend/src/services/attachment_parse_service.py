"""附件文本解析服务。

第一版优先实现确定性、可维护的本地解析：TXT/Markdown/CSV/JSON 直接读取文本；
PDF、Office、图片等复杂格式先记录为不支持解析，避免伪造内容。
后续可以在这里接入 OCR、PDF 解析器或 Office 文档解析器。
"""

from dataclasses import dataclass
from pathlib import Path

from sqlalchemy.orm import Session

from src.core.config import get_settings
from src.core.constants import PARSE_STATUS_COMPLETED, PARSE_STATUS_FAILED
from src.db.models.attachment import Attachment
from src.db.models.parse_result import ParseResult


@dataclass(frozen=True)
class AttachmentParseOutcome:
    """单个附件解析后的可记录结果。"""

    attachment_public_id: str
    file_name: str
    status: str
    text_length: int
    error_message: str | None = None


class AttachmentParseService:
    """读取附件文件并把解析结果写入 parse_results。"""

    TEXT_EXTENSIONS = {".txt", ".md", ".markdown", ".csv", ".json"}

    def __init__(self, db: Session) -> None:
        self.db = db
        self.settings = get_settings()

    def parse_attachment(self, attachment: Attachment) -> AttachmentParseOutcome:
        """解析一个附件，并把结果落库。

        解析服务必须保持幂等：同一个附件重复解析时更新已有 parse_result，
        不重复创建记录，方便用户重试。
        """

        try:
            raw_text = self._extract_text(attachment)
        except Exception as exc:
            attachment.parse_status = PARSE_STATUS_FAILED
            self._upsert_parse_result(
                attachment=attachment,
                parse_status=PARSE_STATUS_FAILED,
                raw_text=None,
                structured_result={
                    "error_message": str(exc),
                    "file_ext": attachment.file_ext,
                },
            )
            return AttachmentParseOutcome(
                attachment_public_id=attachment.public_id,
                file_name=attachment.original_name,
                status=PARSE_STATUS_FAILED,
                text_length=0,
                error_message=str(exc),
            )

        attachment.parse_status = PARSE_STATUS_COMPLETED
        self._upsert_parse_result(
            attachment=attachment,
            parse_status=PARSE_STATUS_COMPLETED,
            raw_text=raw_text,
            structured_result={
                "file_ext": attachment.file_ext,
                "text_length": len(raw_text),
            },
        )
        return AttachmentParseOutcome(
            attachment_public_id=attachment.public_id,
            file_name=attachment.original_name,
            status=PARSE_STATUS_COMPLETED,
            text_length=len(raw_text),
        )

    def _extract_text(self, attachment: Attachment) -> str:
        file_path = self.settings.upload_dir_path / attachment.storage_path
        if not file_path.exists():
            raise FileNotFoundError(f"附件文件不存在：{file_path}")

        file_ext = (attachment.file_ext or "").lower()
        if file_ext not in self.TEXT_EXTENSIONS:
            raise ValueError(
                f"当前仅支持直接解析文本类附件，暂不支持 {file_ext or '未知扩展名'}。"
            )

        return self._read_text_file(file_path)

    @staticmethod
    def _read_text_file(file_path: Path) -> str:
        file_bytes = file_path.read_bytes()
        for encoding in ("utf-8-sig", "utf-8", "gb18030"):
            try:
                text = file_bytes.decode(encoding)
                break
            except UnicodeDecodeError:
                continue
        else:
            raise ValueError("无法识别文本文件编码。")

        normalized_text = text.strip()
        if not normalized_text:
            raise ValueError("附件文本为空，无法解析。")
        return normalized_text

    def _upsert_parse_result(
        self,
        *,
        attachment: Attachment,
        parse_status: str,
        raw_text: str | None,
        structured_result: dict,
    ) -> ParseResult:
        parse_result = attachment.parse_result
        if parse_result is None:
            parse_result = ParseResult(
                attachment_id=attachment.id,
                parser_name="local_text_parser",
                parse_status=parse_status,
                raw_text=raw_text,
                structured_result=structured_result,
            )
            self.db.add(parse_result)
            self.db.flush()
            # 同一轮工作流后续还会读取 attachment.parse_result；
            # 这里显式回填关系，避免必须重新查询数据库才能拿到解析文本。
            attachment.parse_result = parse_result
            return parse_result

        parse_result.parser_name = "local_text_parser"
        parse_result.parse_status = parse_status
        parse_result.raw_text = raw_text
        parse_result.structured_result = structured_result
        self.db.flush()
        return parse_result
