"""Unified answer workflow with backend-default RAG enhancement."""

from dataclasses import replace

from agent.contracts import ActionIntent, AgentTurnContext, AgentTurnResult, RagContext
from agent.rag.context_builder import RagContextBuilder, rag_context_to_snapshot
from agent.runner import LangChainAgentRunner
from src.core.config import Settings, get_settings


class AnswerWorkflow:
    """Generate the assistant answer for normal chat and RAG-enhanced chat."""

    name = "answer_workflow"

    def __init__(
        self,
        runner: LangChainAgentRunner | None = None,
        settings: Settings | None = None,
        rag_context_builder: RagContextBuilder | None = None,
    ) -> None:
        self.settings = settings or get_settings()
        self.runner = runner or LangChainAgentRunner(self.settings)
        self.rag_context_builder = rag_context_builder or RagContextBuilder(self.settings)

    def run(self, context: AgentTurnContext, intent: ActionIntent) -> AgentTurnResult:
        rag_context = self.rag_context_builder.build(context)
        enriched_context = replace(context, rag_context=rag_context)
        result = self.runner.run(enriched_context)
        return self._with_workflow_metadata(result, intent, rag_context)

    def _with_workflow_metadata(
        self,
        result: AgentTurnResult,
        intent: ActionIntent,
        rag_context: RagContext,
    ) -> AgentTurnResult:
        output_snapshot = dict(result.output_snapshot or {})
        output_snapshot["workflow_name"] = self.name
        output_snapshot["intent"] = {
            "type": intent.intent_type,
            "confidence": intent.confidence,
            "source": intent.source,
            "reason": intent.reason,
        }
        output_snapshot["rag"] = rag_context_to_snapshot(rag_context)

        return AgentTurnResult(
            reply_text=result.reply_text,
            intent_type=intent.intent_type,
            workflow_name=self.name,
            model_name=result.model_name,
            output_snapshot=output_snapshot,
        )
