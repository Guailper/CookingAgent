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
from agent.workflows.memory_update_workflow import MemoryUpdateWorkflow
from src.db.models.attachment import Attachment
from src.db.models.conversation import Conversation
from src.db.models.memory_item import MemoryItem
from src.db.models.parse_result import ParseResult
from src.db.models.user import User


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
        ]
        with engine.begin() as connection:
            for statement in statements:
                connection.execute(text(statement))

    def _settings(self):
        return SimpleNamespace(
            upload_dir_path=Path(self.tmp_dir.name),
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

    def test_attachment_parse_workflow_writes_parse_result(self) -> None:
        db = self.SessionLocal()
        attachment = self._create_attachment(db, "note.txt", "番茄炒蛋需要先炒蛋。")

        try:
            with patch("src.services.attachment_parse_service.get_settings", return_value=self._settings()):
                context = self._context("解析这个附件", [attachment.public_id])
                result = AttachmentParseWorkflow(db).run(context, self._intent(context))

            parse_result = db.query(ParseResult).one()
            self.assertEqual(result.workflow_name, "attachment_parse_workflow")
            self.assertIn("已完成 1 个附件解析", result.reply_text)
            self.assertIn("番茄炒蛋", parse_result.raw_text)
        finally:
            db.close()

    def test_document_ingest_workflow_parses_and_indexes_text_attachment(self) -> None:
        db = self.SessionLocal()
        attachment = self._create_attachment(db, "cookbook.txt", "蛋炒饭适合用隔夜米饭。")
        fake_indexing_service = SimpleNamespace(index_document=lambda document: 1)

        try:
            with patch("src.services.attachment_parse_service.get_settings", return_value=self._settings()):
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


if __name__ == "__main__":
    unittest.main()
