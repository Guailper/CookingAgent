"""Data access helpers for the agent_runs table."""

from sqlalchemy import select
from sqlalchemy.orm import Session

from src.db.models.agent_run import AgentRun


class AgentRunRepository:
    """Encapsulate common agent run queries and writes."""

    def __init__(self, db: Session) -> None:
        self.db = db

    def create(self, agent_run: AgentRun) -> AgentRun:
        """Add an agent run to the current transaction."""

        self.db.add(agent_run)
        self.db.flush()
        return agent_run

    def get_by_id(self, agent_run_id: int) -> AgentRun | None:
        """Fetch an agent run by its internal primary key."""

        stmt = select(AgentRun).where(AgentRun.id == agent_run_id)
        return self.db.scalar(stmt)
