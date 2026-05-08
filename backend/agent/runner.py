"""LangChain agent runtime wrapper."""

from agent.contracts import AgentTurnContext, AgentTurnResult
from agent.factories.model_factory import build_chat_model
from agent.factories.tool_factory import build_tools
from agent.memory.message_history import build_langchain_messages
from agent.output.normalizer import build_agent_result
from agent.prompts.system_prompts import build_system_prompt
from src.core.config import Settings, get_settings
from src.core.exceptions import AppException
from src.core.logging import get_logger

logger = get_logger(__name__)


class LangChainAgentRunner:
    """Run one CookingAgent turn through LangChain's agent runtime."""

    def __init__(self, settings: Settings | None = None) -> None:
        self.settings = settings or get_settings()

    def resolve_model_name(self) -> str | None:
        """Return the configured model name for agent_run tracing."""

        return self.settings.agent_model_name or None

    def run(self, context: AgentTurnContext) -> AgentTurnResult:
        """Invoke the LangChain agent and normalize its response."""

        model = build_chat_model(self.settings)

        try:
            from langchain.agents import create_agent
        except ImportError as exc:
            raise AppException(
                500,
                "AGENT_LANGCHAIN_NOT_INSTALLED",
                "Missing langchain dependency. Install backend/requirements.txt first.",
            ) from exc

        tools = build_tools(context)
        messages = build_langchain_messages(
            context,
            max_history_messages=self.settings.agent_max_context_messages,
        )
        system_prompt = build_system_prompt(context)

        logger.info(
            "Starting LangChain agent turn.",
            extra={
                "conversation_public_id": context.conversation_public_id,
                "trigger_message_public_id": context.trigger_message_public_id,
                "provider": self.settings.agent_model_provider,
                "model_name": self.resolve_model_name(),
                "tool_count": len(tools),
                "rag_status": context.rag_context.status if context.rag_context else "none",
            },
        )

        try:
            agent = create_agent(
                model=model,
                tools=tools,
                system_prompt=system_prompt,
            )
            response = agent.invoke({"messages": messages})
        except AppException:
            raise
        except Exception as exc:
            logger.exception("LangChain agent execution failed.", exc_info=exc)
            raise AppException(
                502,
                "AGENT_UPSTREAM_FAILED",
                f"LangChain Agent execution failed: {exc}",
            ) from exc

        return build_agent_result(
            response=response,
            model_name=self.resolve_model_name(),
            provider=self.settings.agent_model_provider,
        )
