"""Unified answer workflow with backend-default RAG enhancement."""

from dataclasses import replace

from agent.contracts import (
    ActionIntent,
    AgentTurnContext,
    AgentTurnResult,
    RagContext,
    WebSearchContext,
)
from agent.rag.citation_validator import CitationValidationResult, CitationValidator
from agent.rag.context_builder import RagContextBuilder, rag_context_to_snapshot
from agent.runner import LangChainAgentRunner
from agent.web.context_builder import WebSearchContextBuilder, web_search_context_to_snapshot
from src.core.config import Settings, get_settings


class AnswerWorkflow:
    """Generate the assistant answer for normal chat and RAG-enhanced chat."""

    name = "answer_workflow"

    def __init__(
        self,
        runner: LangChainAgentRunner | None = None,
        settings: Settings | None = None,
        rag_context_builder: RagContextBuilder | None = None,
        web_search_context_builder: WebSearchContextBuilder | None = None,
        citation_validator: CitationValidator | None = None,
    ) -> None:
        self.settings = settings or get_settings()
        self.runner = runner or LangChainAgentRunner(self.settings)
        self.rag_context_builder = rag_context_builder or RagContextBuilder(self.settings)
        self.web_search_context_builder = (
            web_search_context_builder or WebSearchContextBuilder(self.settings)
        )
        self.citation_validator = citation_validator or CitationValidator()

    def run(self, context: AgentTurnContext, intent: ActionIntent) -> AgentTurnResult:
        rag_context = self.rag_context_builder.build(context)
        web_search_context = self.web_search_context_builder.build(context, rag_context)
        enriched_context = replace(
            context,
            rag_context=rag_context,
            web_search_context=web_search_context,
        )
        refusal = self.citation_validator.refuse_without_evidence(
            context.user_message_text,
            rag_context,
            web_search_context,
        )
        if refusal is not None:
            return self._with_workflow_metadata(
                self._build_guard_result(refusal),
                intent,
                rag_context,
                web_search_context,
                citation_validation=refusal,
            )

        result = self.runner.run(enriched_context)
        return self._with_workflow_metadata(result, intent, rag_context, web_search_context)

    def stream(self, context: AgentTurnContext, intent: ActionIntent):
        """Stream the answer workflow while preserving final workflow metadata."""

        rag_context = self.rag_context_builder.build(context)
        web_search_context = self.web_search_context_builder.build(context, rag_context)
        enriched_context = replace(
            context,
            rag_context=rag_context,
            web_search_context=web_search_context,
        )
        refusal = self.citation_validator.refuse_without_evidence(
            context.user_message_text,
            rag_context,
            web_search_context,
        )
        if refusal is not None:
            yield {"event": "delta", "data": {"content": refusal.reply_text}}
            yield {
                "event": "final",
                "data": self._with_workflow_metadata(
                    self._build_guard_result(refusal),
                    intent,
                    rag_context,
                    web_search_context,
                    citation_validation=refusal,
                ),
            }
            return

        for event in self.runner.stream(enriched_context):
            if event.get("event") != "final":
                yield event
                continue

            result = event.get("data")
            if not isinstance(result, AgentTurnResult):
                yield event
                continue

            validated_result = self._with_workflow_metadata(
                result,
                intent,
                rag_context,
                web_search_context,
            )
            appended_text = validated_result.output_snapshot["citation_validation"].get(
                "appended_text",
                "",
            )
            if appended_text:
                yield {"event": "delta", "data": {"content": appended_text}}

            yield {
                "event": "final",
                "data": validated_result,
            }

    def _with_workflow_metadata(
        self,
        result: AgentTurnResult,
        intent: ActionIntent,
        rag_context: RagContext,
        web_search_context: WebSearchContext,
        citation_validation: CitationValidationResult | None = None,
    ) -> AgentTurnResult:
        citation_validation = citation_validation or self.citation_validator.validate(
            result.reply_text,
            rag_context,
            web_search_context,
        )
        output_snapshot = dict(result.output_snapshot or {})
        output_snapshot["workflow_name"] = self.name
        output_snapshot["intent"] = {
            "type": intent.intent_type,
            "confidence": intent.confidence,
            "source": intent.source,
            "reason": intent.reason,
        }
        output_snapshot["rag"] = rag_context_to_snapshot(rag_context)
        output_snapshot["web_search"] = web_search_context_to_snapshot(web_search_context)
        output_snapshot["citation_validation"] = {
            **citation_validation.to_snapshot(),
            "appended_text": citation_validation.appended_text,
        }

        return AgentTurnResult(
            reply_text=citation_validation.reply_text,
            intent_type=intent.intent_type,
            workflow_name=self.name,
            model_name=result.model_name,
            output_snapshot=output_snapshot,
        )

    def _build_guard_result(self, validation: CitationValidationResult) -> AgentTurnResult:
        return AgentTurnResult(
            reply_text=validation.reply_text,
            intent_type="evidence_guard",
            workflow_name=self.name,
            output_snapshot={"reply_type": "guardrail_text"},
        )
