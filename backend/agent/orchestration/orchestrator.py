"""Select and execute the workflow for one agent turn."""

from agent.contracts import AgentTurnContext, AgentTurnResult
from agent.orchestration.intent_resolver import ActionIntentResolver
from agent.runner import LangChainAgentRunner
from agent.workflows.answer_workflow import AnswerWorkflow
from agent.workflows.attachment_parse_workflow import AttachmentParseWorkflow
from agent.workflows.document_ingest_workflow import DocumentIngestWorkflow
from agent.workflows.memory_update_workflow import MemoryUpdateWorkflow
from sqlalchemy.orm import Session


class AgentOrchestrator:
    """Coordinate intent resolution and workflow dispatch."""

    def __init__(
        self,
        db: Session,
        runner: LangChainAgentRunner | None = None,
        intent_resolver: ActionIntentResolver | None = None,
    ) -> None:
        self.db = db
        self.runner = runner or LangChainAgentRunner()
        self.intent_resolver = intent_resolver or ActionIntentResolver()

    def run(self, context: AgentTurnContext) -> AgentTurnResult:
        intent = self.intent_resolver.resolve(context)
        workflow = self._resolve_workflow(intent.intent_type)
        return workflow.run(context, intent)

    def _resolve_workflow(self, intent_type: str):
        if intent_type == "document_ingest":
            return DocumentIngestWorkflow(self.db, settings=self.runner.settings)
        if intent_type == "attachment_parse":
            return AttachmentParseWorkflow(self.db)
        if intent_type == "memory_update":
            return MemoryUpdateWorkflow(self.db)
        return AnswerWorkflow(runner=self.runner, settings=self.runner.settings)
