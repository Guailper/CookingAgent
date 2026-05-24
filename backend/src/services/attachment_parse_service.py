"""附件解析服务。

文档入库前统一使用 MinerU 生成 Markdown 文本。这里不再保留本地文本直读逻辑，
确保 PDF、Office 和图片等附件走同一套解析链路，便于后续统一定位解析失败。
"""

from dataclasses import dataclass
from pathlib import Path
import subprocess
from uuid import uuid4

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


@dataclass(frozen=True)
class MineruParseResult:
    """MinerU 解析完成后的文本和可追踪元数据。"""

    raw_text: str
    structured_result: dict


class AttachmentParseService:
    """调用 MinerU 解析附件，并把 Markdown 结果写入 parse_results。"""

    PARSER_NAME = "mineru_cli"
    SUPPORTED_EXTENSIONS = {
        ".pdf",
        ".docx",
        ".pptx",
        ".xlsx",
        ".jpg",
        ".jpeg",
        ".png",
    }

    def __init__(self, db: Session) -> None:
        self.db = db
        self.settings = get_settings()

    def parse_attachment(self, attachment: Attachment) -> AttachmentParseOutcome:
        """解析一个附件，并把结果落库。

        解析服务必须保持幂等：同一个附件重复解析时更新已有 parse_result，
        不重复创建记录，方便用户重试。
        """

        try:
            mineru_result = self._parse_with_mineru(attachment)
        except Exception as exc:
            attachment.parse_status = PARSE_STATUS_FAILED
            self._upsert_parse_result(
                attachment=attachment,
                parse_status=PARSE_STATUS_FAILED,
                raw_text=None,
                parser_name=self.PARSER_NAME,
                structured_result={
                    "parser_name": self.PARSER_NAME,
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
            raw_text=mineru_result.raw_text,
            parser_name=self.PARSER_NAME,
            structured_result=mineru_result.structured_result,
        )
        return AttachmentParseOutcome(
            attachment_public_id=attachment.public_id,
            file_name=attachment.original_name,
            status=PARSE_STATUS_COMPLETED,
            text_length=len(mineru_result.raw_text),
        )

    def _parse_with_mineru(self, attachment: Attachment) -> MineruParseResult:
        file_path = self.settings.upload_dir_path / attachment.storage_path
        if not file_path.exists():
            raise FileNotFoundError(f"附件文件不存在：{file_path}")

        file_ext = (attachment.file_ext or "").lower()
        if file_ext not in self.SUPPORTED_EXTENSIONS:
            raise ValueError(
                "当前仅支持 MinerU 可解析的 PDF、DOCX、PPTX、XLSX 和 JPG/PNG 图片附件。"
            )

        output_dir = self._new_output_dir(attachment)
        completed_process = self._run_mineru(file_path, output_dir)
        markdown_path = self._find_markdown_file(output_dir, file_path.stem)
        raw_text = markdown_path.read_text(encoding="utf-8").strip()
        if not raw_text:
            raise ValueError("MinerU 已完成解析，但生成的 Markdown 文本为空。")

        return MineruParseResult(
            raw_text=raw_text,
            structured_result={
                "parser_name": self.PARSER_NAME,
                "file_ext": attachment.file_ext,
                "text_length": len(raw_text),
                "mineru_output_dir": self._display_path(output_dir),
                "mineru_markdown_path": self._display_path(markdown_path),
                "mineru_backend": self.settings.mineru_backend,
                "mineru_method": self.settings.mineru_method,
                "mineru_lang": self.settings.mineru_lang,
                "mineru_api_url": self.settings.mineru_api_url or None,
                "mineru_stdout": self._truncate_process_text(completed_process.stdout),
            },
        )

    def _new_output_dir(self, attachment: Attachment) -> Path:
        output_dir = (
            self.settings.mineru_output_dir_path
            / attachment.public_id
            / f"parse_{uuid4().hex}"
        )
        output_dir.mkdir(parents=True, exist_ok=True)
        return output_dir

    def _run_mineru(self, file_path: Path, output_dir: Path) -> subprocess.CompletedProcess[str]:
        command = self._build_mineru_command(file_path, output_dir)

        try:
            completed_process = subprocess.run(
                command,
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=self.settings.mineru_parse_timeout_seconds,
                check=False,
            )
        except FileNotFoundError as exc:
            raise RuntimeError(
                f"未找到 MinerU 命令：{self.settings.mineru_command}。请安装 MinerU 或配置 MINERU_COMMAND。"
            ) from exc
        except subprocess.TimeoutExpired as exc:
            raise RuntimeError(
                f"MinerU 解析超时，已超过 {self.settings.mineru_parse_timeout_seconds} 秒。"
            ) from exc

        if completed_process.returncode != 0:
            stderr = self._truncate_process_text(completed_process.stderr)
            stdout = self._truncate_process_text(completed_process.stdout)
            raise RuntimeError(
                f"MinerU 解析失败，退出码 {completed_process.returncode}。stderr={stderr} stdout={stdout}"
            )

        return completed_process

    def _build_mineru_command(self, file_path: Path, output_dir: Path) -> list[str]:
        command = [
            self.settings.mineru_command,
            "-p",
            str(file_path),
            "-o",
            str(output_dir),
        ]

        if self.settings.mineru_backend:
            command.extend(["-b", self.settings.mineru_backend])
        if self.settings.mineru_method:
            command.extend(["-m", self.settings.mineru_method])
        if self.settings.mineru_lang:
            command.extend(["-l", self.settings.mineru_lang])
        if self.settings.mineru_api_url:
            command.extend(["--api-url", self.settings.mineru_api_url])

        # 预留给 MinerU 新版本或部署侧的额外参数，例如并发、设备或模型源。
        command.extend(self.settings.mineru_extra_args)
        return command

    def _find_markdown_file(self, output_dir: Path, source_stem: str) -> Path:
        markdown_files = [path for path in output_dir.rglob("*.md") if path.is_file()]
        if not markdown_files:
            raise FileNotFoundError(f"MinerU 没有在输出目录中生成 Markdown：{output_dir}")

        preferred_names = {
            f"{source_stem}.md".lower(),
            "full.md",
            "middle.md",
        }
        for path in markdown_files:
            if path.name.lower() in preferred_names:
                return path

        return max(markdown_files, key=lambda path: path.stat().st_size)

    def _upsert_parse_result(
        self,
        *,
        attachment: Attachment,
        parse_status: str,
        raw_text: str | None,
        parser_name: str,
        structured_result: dict,
    ) -> ParseResult:
        parse_result = attachment.parse_result
        if parse_result is None:
            parse_result = ParseResult(
                attachment_id=attachment.id,
                parser_name=parser_name,
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

        parse_result.parser_name = parser_name
        parse_result.parse_status = parse_status
        parse_result.raw_text = raw_text
        parse_result.structured_result = structured_result
        self.db.flush()
        return parse_result

    def _display_path(self, path: Path) -> str:
        resolved_path = path.resolve()
        project_root = Path(self.settings.project_root).resolve()
        try:
            return str(resolved_path.relative_to(project_root))
        except ValueError:
            return str(resolved_path)

    @staticmethod
    def _truncate_process_text(text: str | None, max_length: int = 2000) -> str:
        normalized_text = (text or "").strip()
        if len(normalized_text) <= max_length:
            return normalized_text
        return f"{normalized_text[:max_length]}..."
