"""Tests for non-answer agent workflows."""

import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

from agent.contracts import AgentTurnContext
from agent.orchestration.intent_resolver import ActionIntentResolver
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
from src.services.conversation_summary_service import ConversationSummaryService


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

    def _settings(self):
        return SimpleNamespace(
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
            rag_default_knowledge_base_ids=["cookbook"],
            rag_chunk_target_size=700,
            rag_chunk_max_size=1000,
            rag_chunk_overlap_size=100,
        )

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

    def _fake_mineru_run(self, markdown_text: str):
        def run(command, **kwargs):
            _ = kwargs
            output_dir = Path(command[command.index("-o") + 1])
            markdown_dir = output_dir / "auto"
            markdown_dir.mkdir(parents=True, exist_ok=True)
            (markdown_dir / "full.md").write_text(markdown_text, encoding="utf-8")
            return SimpleNamespace(returncode=0, stdout="mineru ok", stderr="")

        return run

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
                ).run(context, self._intent(context))

            parse_result = db.query(ParseResult).one()
            self.assertEqual(result.workflow_name, "document_ingest_workflow")
            self.assertIn("已将 1 个文档写入默认知识库", result.reply_text)
            self.assertEqual(parse_result.embedding_status, "completed")
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
