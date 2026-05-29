"""Tests for non-answer agent workflows."""

import asyncio
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch

from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

from agent.contracts import AgentTurnContext
from agent.orchestration.intent_resolver import ActionIntentResolver, IntentPrediction
from agent.workflows.attachment_parse_workflow import AttachmentParseWorkflow
from agent.workflows.document_ingest_workflow import DocumentIngestWorkflow
from agent.workflows.memory_update_workflow import (
    MemoryExtractionItem,
    MemoryExtractionResult,
    MemoryUpdateWorkflow,
)
from src.db.models.attachment import Attachment
from src.db.models.conversation import Conversation
from src.db.models.conversation_summary import ConversationSummary
from src.db.models.memory_item import MemoryItem
from src.db.models.message import Message
from src.db.models.parse_result import ParseResult
from src.db.models.user import User
from src.services.attachment_content_validation_service import (
    CONTENT_VALIDATION_STATUS_COMPLETED,
    CONTENT_VALIDATION_STATUS_FAILED,
    AttachmentContentValidation,
    AttachmentContentValidationService,
    ContentValidationModelResult,
)
from src.services.conversation_summary_service import ConversationSummaryService
from src.services.file_service import FileService


class _FakeUploadFile:
    def __init__(
        self,
        *,
        filename: str,
        content: bytes,
        content_type: str = "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    ) -> None:
        self.filename = filename
        self.content_type = content_type
        self._content = content

    async def read(self) -> bytes:
        return self._content


class _FakeIntentModelClassifier:
    def __init__(self, prediction: IntentPrediction) -> None:
        self.prediction = prediction

    def predict(self, context: AgentTurnContext) -> IntentPrediction:
        _ = context
        return self.prediction


class AgentWorkflowTests(unittest.TestCase):
    """Use an in-memory database so workflow tests stay deterministic."""

    def setUp(self) -> None:
        self.engine = create_engine("sqlite+pysqlite:///:memory:")
        self._create_sqlite_schema(self.engine)
        self.SessionLocal = sessionmaker(bind=self.engine, expire_on_commit=False)
        self.tmp_dir = tempfile.TemporaryDirectory()

    def tearDown(self) -> None:
        self.tmp_dir.cleanup()
        self.engine.dispose()

    def _create_sqlite_schema(self, engine) -> None:
        """只建工作流测试需要的最小表，避开 MySQL 专用 DDL。"""

        statements = [
            """
            CREATE TABLE users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                public_id VARCHAR(64) NOT NULL UNIQUE,
                username VARCHAR(100) NOT NULL,
                email VARCHAR(191) NOT NULL UNIQUE,
                password_hash VARCHAR(255) NOT NULL,
                status VARCHAR(32) NOT NULL DEFAULT 'active',
                last_login_at DATETIME,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP NOT NULL,
                updated_at DATETIME DEFAULT CURRENT_TIMESTAMP NOT NULL
            )
            """,
            """
            CREATE TABLE conversations (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                public_id VARCHAR(64) NOT NULL UNIQUE,
                user_id INTEGER NOT NULL,
                title VARCHAR(255) NOT NULL DEFAULT 'test',
                status VARCHAR(32) NOT NULL DEFAULT 'active',
                latest_message_at DATETIME,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP NOT NULL,
                updated_at DATETIME DEFAULT CURRENT_TIMESTAMP NOT NULL
            )
            """,
            """
            CREATE TABLE attachments (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                public_id VARCHAR(64) NOT NULL UNIQUE,
                conversation_id INTEGER NOT NULL,
                message_id INTEGER,
                original_name VARCHAR(255) NOT NULL,
                stored_name VARCHAR(255) NOT NULL,
                file_ext VARCHAR(20) NOT NULL,
                mime_type VARCHAR(100) NOT NULL,
                file_size BIGINT NOT NULL,
                attachment_kind VARCHAR(32) NOT NULL DEFAULT 'document',
                storage_provider VARCHAR(32) NOT NULL DEFAULT 'local',
                storage_path VARCHAR(1024) NOT NULL,
                file_hash VARCHAR(128),
                parse_status VARCHAR(32) NOT NULL DEFAULT 'pending',
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP NOT NULL,
                updated_at DATETIME DEFAULT CURRENT_TIMESTAMP NOT NULL
            )
            """,
            """
            CREATE TABLE messages (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                public_id VARCHAR(64) NOT NULL UNIQUE,
                conversation_id INTEGER NOT NULL,
                user_id INTEGER,
                role VARCHAR(32) NOT NULL,
                message_type VARCHAR(32) NOT NULL DEFAULT 'text',
                content TEXT NOT NULL DEFAULT '',
                status VARCHAR(32) NOT NULL DEFAULT 'completed',
                extra_metadata JSON,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP NOT NULL,
                updated_at DATETIME DEFAULT CURRENT_TIMESTAMP NOT NULL
            )
            """,
            """
            CREATE TABLE parse_results (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                attachment_id INTEGER NOT NULL UNIQUE,
                parser_name VARCHAR(100) NOT NULL,
                parse_status VARCHAR(32) NOT NULL DEFAULT 'completed',
                embedding_status VARCHAR(32) NOT NULL DEFAULT 'pending',
                raw_text TEXT,
                structured_result JSON,
                ocr_result JSON,
                started_at DATETIME,
                completed_at DATETIME,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP NOT NULL,
                updated_at DATETIME DEFAULT CURRENT_TIMESTAMP NOT NULL
            )
            """,
            """
            CREATE TABLE memory_items (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                public_id VARCHAR(64) NOT NULL UNIQUE,
                user_public_id VARCHAR(64) NOT NULL,
                conversation_public_id VARCHAR(64),
                source_message_public_id VARCHAR(64),
                memory_type VARCHAR(64) NOT NULL,
                content TEXT NOT NULL,
                confidence VARCHAR(16) NOT NULL DEFAULT '1.0',
                extra_metadata JSON,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP NOT NULL,
                updated_at DATETIME DEFAULT CURRENT_TIMESTAMP NOT NULL
            )
            """,
            """
            CREATE TABLE conversation_summaries (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                conversation_id INTEGER NOT NULL UNIQUE,
                conversation_public_id VARCHAR(64) NOT NULL UNIQUE,
                summary_text TEXT NOT NULL DEFAULT '',
                covered_until_message_public_id VARCHAR(64),
                source_message_count INTEGER NOT NULL DEFAULT 0,
                model_name VARCHAR(100),
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP NOT NULL,
                updated_at DATETIME DEFAULT CURRENT_TIMESTAMP NOT NULL
            )
            """,
        ]
        with engine.begin() as connection:
            for statement in statements:
                connection.execute(text(statement))

    def _settings(self, **overrides):
        defaults = dict(
            project_root=str(Path(self.tmp_dir.name)),
            upload_dir_path=Path(self.tmp_dir.name),
            mineru_command="mineru",
            mineru_output_dir_path=Path(self.tmp_dir.name) / "mineru",
            mineru_backend="pipeline",
            mineru_method="auto",
            mineru_lang="ch",
            mineru_api_url="",
            mineru_parse_timeout_seconds=30,
            mineru_extra_args=[],
            max_message_attachments=5,
            max_upload_size_mb=10,
            rag_default_knowledge_base_ids=["cookbook"],
            rag_chunk_target_size=700,
            rag_chunk_max_size=1000,
            rag_chunk_overlap_size=100,
            intent_rule_weight=0.6,
            intent_model_weight=0.4,
            intent_model_provider="disabled",
            intent_model_base_url="",
            intent_model_api_key="not-needed",
            intent_model_name="",
            content_validation_model_provider="local",
            content_validation_model_base_url="http://127.0.0.1:11434/v1",
            content_validation_model_api_key="not-needed",
            content_validation_model_name="qwen2.5:3b",
        )
        defaults.update(overrides)
        return SimpleNamespace(**defaults)

    def _context(self, text: str, attachment_ids: list[str] | None = None) -> AgentTurnContext:
        return AgentTurnContext(
            conversation_public_id="conv_test",
            user_public_id="user_test",
            trigger_message_public_id="msg_test",
            user_message_text=text,
            attachment_public_ids=attachment_ids or [],
            knowledge_base_public_ids=["cookbook"],
        )

    def _intent(self, context: AgentTurnContext):
        return ActionIntentResolver().resolve(context)

    @staticmethod
    def _run_async(coro):
        return asyncio.run(coro)

    def _create_attachment(self, db, file_name: str, content: str) -> Attachment:
        user = User(
            public_id="user_test",
            username="tester",
            email="tester@example.com",
            password_hash="hash",
        )
        conversation = Conversation(
            public_id="conv_test",
            user=user,
            title="test",
        )
        stored_path = Path(self.tmp_dir.name) / file_name
        stored_path.write_text(content, encoding="utf-8")
        attachment = Attachment(
            public_id="att_test",
            conversation=conversation,
            original_name=file_name,
            stored_name=file_name,
            file_ext=Path(file_name).suffix,
            mime_type="text/plain",
            file_size=stored_path.stat().st_size,
            storage_path=file_name,
            file_hash="hash",
        )
        db.add_all([user, conversation, attachment])
        db.commit()
        return attachment

    def _create_conversation_with_messages(self, db, count: int = 4) -> Conversation:
        user = User(
            public_id="user_summary",
            username="summary-tester",
            email="summary@example.com",
            password_hash="hash",
        )
        conversation = Conversation(
            public_id="conv_summary",
            user=user,
            title="summary",
        )
        db.add_all([user, conversation])
        db.flush()

        for index in range(count):
            db.add(
                Message(
                    public_id=f"msg_summary_{index}",
                    conversation_id=conversation.id,
                    user_id=user.id if index % 2 == 0 else None,
                    role="user" if index % 2 == 0 else "assistant",
                    content=f"summary message {index}",
                )
            )

        db.commit()
        return conversation

    def test_intent_resolver_routes_side_effect_workflows(self) -> None:
        resolver = ActionIntentResolver()

        ingest = resolver.resolve(self._context("请把这个文件加入知识库", ["att_1"]))
        parse = resolver.resolve(self._context("解析这个附件", ["att_1"]))
        memory = resolver.resolve(self._context("记住我不吃香菜"))
        answer = resolver.resolve(self._context("鸡蛋和米饭怎么做"))

        self.assertEqual(ingest.intent_type, "document_ingest")
        self.assertEqual(parse.intent_type, "attachment_parse")
        self.assertEqual(memory.intent_type, "memory_update")
        self.assertEqual(answer.intent_type, "answer")

    def test_intent_resolver_fuses_model_and_rule_weights(self) -> None:
        resolver = ActionIntentResolver(
            settings=self._settings(intent_rule_weight=0.2, intent_model_weight=0.8),
            model_classifier=_FakeIntentModelClassifier(
                IntentPrediction(
                    intent_type="memory_update",
                    confidence=0.95,
                    source="model",
                    reason="用户表达了长期忌口。",
                )
            ),
        )

        intent = resolver.resolve(self._context("以后推荐清淡一点"))

        self.assertEqual(intent.intent_type, "memory_update")
        self.assertEqual(intent.source, "hybrid")
        self.assertAlmostEqual(intent.confidence, 0.76)
        self.assertIn("融合分数", intent.reason)

    def test_intent_resolver_keeps_rule_result_when_model_unavailable(self) -> None:
        resolver = ActionIntentResolver(
            settings=self._settings(intent_rule_weight=0.6, intent_model_weight=0.4),
            model_classifier=_FakeIntentModelClassifier(
                IntentPrediction(
                    intent_type="answer",
                    confidence=0.0,
                    source="model",
                    reason="本地模型未启用。",
                    available=False,
                )
            ),
        )

        intent = resolver.resolve(self._context("记住我不吃香菜"))

        self.assertEqual(intent.intent_type, "memory_update")
        self.assertEqual(intent.source, "rule")
        self.assertIn("降级使用规则结果", intent.reason)

    def test_intent_resolver_requires_rule_confirmation_for_attachment_side_effects(self) -> None:
        resolver = ActionIntentResolver(
            settings=self._settings(intent_rule_weight=0.1, intent_model_weight=0.9),
            model_classifier=_FakeIntentModelClassifier(
                IntentPrediction(
                    intent_type="document_ingest",
                    confidence=0.99,
                    source="model",
                    reason="模型认为用户想入库附件。",
                )
            ),
        )

        intent = resolver.resolve(self._context("这份材料讲了什么？", ["att_1"]))

        self.assertEqual(intent.intent_type, "answer")
        self.assertIn("安全策略", intent.reason)

    def _fake_mineru_run(self, markdown_text: str):
        def run(command, **kwargs):
            _ = kwargs
            output_dir = Path(command[command.index("-o") + 1])
            markdown_dir = output_dir / "auto"
            markdown_dir.mkdir(parents=True, exist_ok=True)
            (markdown_dir / "full.md").write_text(markdown_text, encoding="utf-8")
            return SimpleNamespace(returncode=0, stdout="mineru ok", stderr="")

        return run

    @staticmethod
    def _content_validation_service(
        *,
        accepted: bool = True,
        category: str = "cooking_related",
        confidence: float = 0.95,
        reason: str = "文档主体为可复用的烹饪资料。",
        status: str = CONTENT_VALIDATION_STATUS_COMPLETED,
        error_message: str | None = None,
    ):
        return SimpleNamespace(
            validate=Mock(
                return_value=AttachmentContentValidation(
                    accepted=accepted,
                    category=category,
                    confidence=confidence,
                    reason=reason,
                    status=status,
                    model_provider="local",
                    model_name="qwen2.5:3b",
                    error_message=error_message,
                )
            )
        )

    def test_attachment_parse_workflow_writes_parse_result(self) -> None:
        db = self.SessionLocal()
        attachment = self._create_attachment(db, "note.pdf", "fake pdf bytes")

        try:
            with patch("src.services.attachment_parse_service.get_settings", return_value=self._settings()), patch(
                "src.services.attachment_parse_service.subprocess.run",
                side_effect=self._fake_mineru_run("番茄炒蛋需要先炒蛋。"),
            ):
                context = self._context("解析这个附件", [attachment.public_id])
                result = AttachmentParseWorkflow(db).run(context, self._intent(context))

            parse_result = db.query(ParseResult).one()
            self.assertEqual(result.workflow_name, "attachment_parse_workflow")
            self.assertIn("已完成 1 个附件解析", result.reply_text)
            self.assertIn("番茄炒蛋", parse_result.raw_text)
            self.assertEqual(parse_result.parser_name, "mineru_cli")
            self.assertEqual(parse_result.structured_result["parser_name"], "mineru_cli")
        finally:
            db.close()

    def test_document_ingest_workflow_parses_with_mineru_and_indexes_attachment(self) -> None:
        db = self.SessionLocal()
        attachment = self._create_attachment(db, "cookbook.pdf", "fake pdf bytes")
        fake_indexing_service = SimpleNamespace(index_document=lambda document: 1)

        try:
            with patch("src.services.attachment_parse_service.get_settings", return_value=self._settings()), patch(
                "src.services.attachment_parse_service.subprocess.run",
                side_effect=self._fake_mineru_run("蛋炒饭适合用隔夜米饭。"),
            ):
                context = self._context("请把这个文件加入知识库", [attachment.public_id])
                result = DocumentIngestWorkflow(
                    db,
                    settings=self._settings(),
                    indexing_service=fake_indexing_service,
                    content_validation_service=self._content_validation_service(),
                ).run(context, self._intent(context))

            parse_result = db.query(ParseResult).one()
            self.assertEqual(result.workflow_name, "document_ingest_workflow")
            self.assertIn("已将 1 个文档写入默认知识库", result.reply_text)
            self.assertEqual(parse_result.embedding_status, "completed")
            self.assertEqual(
                parse_result.structured_result["content_validation"]["model_name"],
                "qwen2.5:3b",
            )
        finally:
            db.close()

    def test_upload_service_stores_attachment_then_ingest_workflow_indexes_it(self) -> None:
        db = self.SessionLocal()
        user = User(
            public_id="user_upload",
            username="upload-tester",
            email="upload@example.com",
            password_hash="hash",
        )
        conversation = Conversation(
            public_id="conv_upload",
            user=user,
            title="upload",
        )
        db.add_all([user, conversation])
        db.commit()
        fake_indexing_service = SimpleNamespace(index_document=Mock(return_value=3))

        try:
            with patch("src.services.file_service.get_settings", return_value=self._settings()):
                uploaded = self._run_async(
                    FileService(db).upload_conversation_attachments(
                        user=user,
                        conversation_public_id=conversation.public_id,
                        files=[
                            _FakeUploadFile(
                                filename="upload-recipe.docx",
                                content=b"fake docx bytes for upload test",
                            )
                        ],
                    )
                )

            self.assertEqual(len(uploaded), 1)
            attachment = uploaded[0]
            self.assertEqual(attachment.original_name, "upload-recipe.docx")
            self.assertEqual(attachment.file_ext, ".docx")
            self.assertTrue((Path(self.tmp_dir.name) / attachment.storage_path).exists())

            with patch("src.services.attachment_parse_service.get_settings", return_value=self._settings()), patch(
                "src.services.attachment_parse_service.subprocess.run",
                side_effect=self._fake_mineru_run("番茄炒蛋：鸡蛋先炒至凝固，再下番茄收汁。"),
            ):
                context = AgentTurnContext(
                    conversation_public_id=conversation.public_id,
                    user_public_id=user.public_id,
                    trigger_message_public_id="msg_upload",
                    user_message_text="请把这个附件加入知识库",
                    attachment_public_ids=[attachment.public_id],
                    knowledge_base_public_ids=["cookbook"],
                )
                result = DocumentIngestWorkflow(
                    db,
                    settings=self._settings(),
                    indexing_service=fake_indexing_service,
                    content_validation_service=self._content_validation_service(),
                ).run(context, self._intent(context))

            parse_result = db.query(ParseResult).one()
            self.assertIn("已将 1 个文档写入默认知识库", result.reply_text)
            self.assertEqual(parse_result.embedding_status, "completed")
            fake_indexing_service.index_document.assert_called_once()
            indexed_document = fake_indexing_service.index_document.call_args.args[0]
            self.assertEqual(indexed_document.document_public_id, attachment.public_id)
            self.assertIn("番茄炒蛋", indexed_document.text)
        finally:
            db.close()

    def test_document_ingest_workflow_rejects_non_cooking_content(self) -> None:
        db = self.SessionLocal()
        attachment = self._create_attachment(db, "quarterly-report.pdf", "fake pdf bytes")
        index_document = Mock(return_value=1)
        fake_indexing_service = SimpleNamespace(index_document=index_document)

        try:
            with patch("src.services.attachment_parse_service.get_settings", return_value=self._settings()), patch(
                "src.services.attachment_parse_service.subprocess.run",
                side_effect=self._fake_mineru_run("本季度营业收入同比增长，项目预算执行情况稳定。"),
            ):
                context = self._context("请把这个文件加入知识库", [attachment.public_id])
                result = DocumentIngestWorkflow(
                    db,
                    settings=self._settings(),
                    indexing_service=fake_indexing_service,
                    content_validation_service=self._content_validation_service(
                        accepted=False,
                        category="irrelevant",
                        confidence=0.98,
                        reason="文档主体为经营报告，与烹饪知识无关。",
                    ),
                ).run(context, self._intent(context))

            parse_result = db.query(ParseResult).one()
            index_document.assert_not_called()
            self.assertEqual(parse_result.embedding_status, "rejected")
            self.assertIn("主题分类模型未确认", result.reply_text)
            self.assertEqual(
                result.output_snapshot["skipped_documents"][0]["reason"],
                "irrelevant_content",
            )
            self.assertFalse(
                parse_result.structured_result["content_validation"]["accepted"]
            )
        finally:
            db.close()

    def test_content_validation_service_uses_dedicated_structured_model(self) -> None:
        class _FakeStructuredModel:
            def invoke(self, messages):
                self.messages = messages
                return ContentValidationModelResult(
                    accepted=True,
                    category="cooking_related",
                    confidence=0.94,
                    reason="内容描述了完整做菜步骤。",
                )

        class _FakeModel:
            def with_structured_output(self, schema):
                self.schema = schema
                return _FakeStructuredModel()

        build_model = Mock(return_value=_FakeModel())
        with patch(
            "src.services.attachment_content_validation_service.build_chat_model",
            build_model,
        ):
            validation = AttachmentContentValidationService(self._settings()).validate(
                title="晚餐菜谱.pdf",
                text="一份可复用的做菜说明。",
            )

        model_config = build_model.call_args.args[1]
        self.assertEqual(model_config.provider, "local")
        self.assertEqual(model_config.base_url, "http://127.0.0.1:11434/v1")
        self.assertEqual(model_config.model_name, "qwen2.5:3b")
        self.assertEqual(build_model.call_args.kwargs["temperature"], 0.0)
        self.assertTrue(validation.accepted)
        self.assertEqual(validation.category, "cooking_related")
        self.assertEqual(validation.status, CONTENT_VALIDATION_STATUS_COMPLETED)

    def test_content_validation_service_fails_closed_when_model_call_fails(self) -> None:
        with patch(
            "src.services.attachment_content_validation_service.build_chat_model",
            side_effect=RuntimeError("validation model timeout"),
        ):
            validation = AttachmentContentValidationService(self._settings()).validate(
                title="unknown.pdf",
                text="无法在模型不可用时自动确认主题。",
            )

        self.assertFalse(validation.accepted)
        self.assertEqual(validation.category, "uncertain")
        self.assertEqual(validation.status, CONTENT_VALIDATION_STATUS_FAILED)
        self.assertEqual(validation.error_message, "validation model timeout")

    def test_content_validation_service_rejects_low_confidence_related_result(self) -> None:
        class _LowConfidenceStructuredModel:
            def invoke(self, messages):
                _ = messages
                return ContentValidationModelResult(
                    accepted=True,
                    category="cooking_related",
                    confidence=0.35,
                    reason="内容可能涉及餐食准备。",
                )

        class _LowConfidenceModel:
            def with_structured_output(self, schema):
                _ = schema
                return _LowConfidenceStructuredModel()

        with patch(
            "src.services.attachment_content_validation_service.build_chat_model",
            return_value=_LowConfidenceModel(),
        ):
            validation = AttachmentContentValidationService(self._settings()).validate(
                title="mixed-notes.pdf",
                text="这是一份主题混杂的文档。",
            )

        self.assertFalse(validation.accepted)
        self.assertEqual(validation.category, "uncertain")
        self.assertIn("置信度不足", validation.reason)

    def test_document_ingest_workflow_keeps_validation_failure_retryable(self) -> None:
        db = self.SessionLocal()
        attachment = self._create_attachment(db, "cookbook.pdf", "fake pdf bytes")
        index_document = Mock(return_value=1)

        try:
            with patch("src.services.attachment_parse_service.get_settings", return_value=self._settings()), patch(
                "src.services.attachment_parse_service.subprocess.run",
                side_effect=self._fake_mineru_run("一份待判定的附件正文。"),
            ):
                context = self._context("请把这个文件加入知识库", [attachment.public_id])
                result = DocumentIngestWorkflow(
                    db,
                    settings=self._settings(),
                    indexing_service=SimpleNamespace(index_document=index_document),
                    content_validation_service=self._content_validation_service(
                        accepted=False,
                        category="uncertain",
                        confidence=0.0,
                        reason="主题校验模型暂时无法完成判定，附件未写入知识库。",
                        status=CONTENT_VALIDATION_STATUS_FAILED,
                        error_message="validation model timeout",
                    ),
                ).run(context, self._intent(context))

            parse_result = db.query(ParseResult).one()
            index_document.assert_not_called()
            self.assertEqual(parse_result.embedding_status, "failed")
            self.assertEqual(
                result.output_snapshot["skipped_documents"][0]["reason"],
                "validation_failed",
            )
            self.assertIn("稍后重试", result.reply_text)
        finally:
            db.close()

    def test_document_ingest_retry_reuses_existing_attachment_after_index_failure(self) -> None:
        db = self.SessionLocal()
        attachment = self._create_attachment(db, "retry-cookbook.pdf", "fake pdf bytes")
        failed_index_document = Mock(side_effect=RuntimeError("milvus unavailable"))
        successful_index_document = Mock(return_value=2)

        try:
            with patch("src.services.attachment_parse_service.get_settings", return_value=self._settings()), patch(
                "src.services.attachment_parse_service.subprocess.run",
                side_effect=self._fake_mineru_run("番茄炒蛋的食材包括番茄和鸡蛋，先炒蛋再下番茄。"),
            ) as mineru_run:
                context = self._context("请把这个文件加入知识库", [attachment.public_id])
                first_result = DocumentIngestWorkflow(
                    db,
                    settings=self._settings(),
                    indexing_service=SimpleNamespace(index_document=failed_index_document),
                    content_validation_service=self._content_validation_service(),
                ).run(context, self._intent(context))
                self.assertEqual(db.query(ParseResult).one().embedding_status, "failed")

                second_result = DocumentIngestWorkflow(
                    db,
                    settings=self._settings(),
                    indexing_service=SimpleNamespace(index_document=successful_index_document),
                    content_validation_service=self._content_validation_service(),
                ).run(context, self._intent(context))

            parse_result = db.query(ParseResult).one()
            self.assertEqual(first_result.output_snapshot["skipped_documents"][0]["reason"], "index_failed")
            self.assertIn("已将 1 个文档写入默认知识库", second_result.reply_text)
            self.assertEqual(second_result.output_snapshot["indexed_documents"][0]["attachment_public_id"], attachment.public_id)
            self.assertEqual(parse_result.embedding_status, "completed")
            self.assertEqual(mineru_run.call_count, 1)
            successful_index_document.assert_called_once()
        finally:
            db.close()

    def test_memory_update_workflow_saves_user_preference(self) -> None:
        db = self.SessionLocal()
        context = self._context("记住我不吃香菜")

        try:
            result = MemoryUpdateWorkflow(db).run(context, self._intent(context))

            memory = db.query(MemoryItem).one()
            self.assertEqual(result.workflow_name, "memory_update_workflow")
            self.assertIn("已记住 1 条偏好", result.reply_text)
            self.assertEqual(memory.memory_type, "diet_restriction")
            self.assertIn("不吃香菜", memory.content)
        finally:
            db.close()

    def test_memory_update_workflow_uses_langchain_structured_output(self) -> None:
        db = self.SessionLocal()
        context = self._context("以后给我推荐少油少盐的菜")

        class _FakeStructuredModel:
            def invoke(self, messages):
                _ = messages
                return MemoryExtractionResult(
                    memories=[
                        MemoryExtractionItem(
                            memory_type="health_goal",
                            content="用户偏好少油少盐的菜",
                            confidence=0.88,
                        )
                    ]
                )

        class _FakeModel:
            def with_structured_output(self, schema):
                self.schema = schema
                return _FakeStructuredModel()

        try:
            with patch(
                "agent.workflows.memory_update_workflow.build_chat_model",
                return_value=_FakeModel(),
            ):
                result = MemoryUpdateWorkflow(db).run(context, self._intent(context))

            memory = db.query(MemoryItem).one()
            self.assertEqual(result.workflow_name, "memory_update_workflow")
            self.assertEqual(memory.memory_type, "health_goal")
            self.assertEqual(memory.content, "用户偏好少油少盐的菜")
            self.assertEqual(memory.extra_metadata["extractor"], "langchain_structured")
        finally:
            db.close()

    def test_memory_update_workflow_updates_existing_memory_when_explicit(self) -> None:
        db = self.SessionLocal()
        original_memory = MemoryItem(
            public_id="mem_existing",
            user_public_id="user_test",
            conversation_public_id="conv_old",
            source_message_public_id="msg_old",
            memory_type="taste_preference",
            content="用户喜欢清淡口味",
            confidence="0.80",
            extra_metadata={"extractor": "test"},
        )
        db.add(original_memory)
        db.commit()
        context = self._context("更新我的口味偏好：现在喜欢酸甜口")

        class _FakeStructuredModel:
            def invoke(self, messages):
                _ = messages
                return MemoryExtractionResult(
                    memories=[
                        MemoryExtractionItem(
                            memory_type="taste_preference",
                            content="用户喜欢酸甜口",
                            confidence=0.91,
                        )
                    ]
                )

        class _FakeModel:
            def with_structured_output(self, schema):
                self.schema = schema
                return _FakeStructuredModel()

        try:
            with patch(
                "agent.workflows.memory_update_workflow.build_chat_model",
                return_value=_FakeModel(),
            ):
                result = MemoryUpdateWorkflow(db).run(context, self._intent(context))

            memories = db.query(MemoryItem).all()
            self.assertEqual(len(memories), 1)
            self.assertEqual(memories[0].public_id, "mem_existing")
            self.assertEqual(memories[0].content, "用户喜欢酸甜口")
            self.assertEqual(memories[0].confidence, "0.91")
            self.assertEqual(memories[0].extra_metadata["last_operation"], "update")
            self.assertEqual(
                memories[0].extra_metadata["update_history"][0]["content"],
                "用户喜欢清淡口味",
            )
            self.assertEqual(len(result.output_snapshot["updated_memories"]), 1)
            self.assertEqual(result.output_snapshot["created_memories"], [])
        finally:
            db.close()

    def test_conversation_summary_service_updates_with_model(self) -> None:
        db = self.SessionLocal()
        conversation = self._create_conversation_with_messages(db, count=4)

        class _FakeSummaryModel:
            def invoke(self, messages):
                return SimpleNamespace(content="当前目标：做一份快手晚餐。\n已确认约束：不吃香菜。")

        settings = SimpleNamespace(
            agent_model_name="summary-model",
            agent_model_candidates=[],
            agent_summary_trigger_messages=3,
            agent_summary_batch_messages=2,
            agent_summary_max_chars=500,
            agent_model_provider="openai",
            agent_model_base_url="https://example.com/v1",
            agent_model_api_key="test-key",
            agent_request_timeout_seconds=30,
            agent_temperature=0.4,
            agent_max_output_tokens=512,
            agent_disable_reasoning=False,
        )

        try:
            with patch(
                "src.services.conversation_summary_service.build_chat_model",
                return_value=_FakeSummaryModel(),
            ):
                summary = ConversationSummaryService(db, settings=settings).update_after_answer(
                    conversation
                )

            saved_summary = db.query(ConversationSummary).one()
            self.assertIsNotNone(summary)
            self.assertIn("当前目标", saved_summary.summary_text)
            self.assertEqual(saved_summary.covered_until_message_public_id, "msg_summary_3")
            self.assertEqual(saved_summary.source_message_count, 4)
            self.assertEqual(saved_summary.model_name, "summary-model")
        finally:
            db.close()


if __name__ == "__main__":
    unittest.main()
