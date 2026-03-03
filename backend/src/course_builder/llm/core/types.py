from __future__ import annotations

from langchain_core.messages import BaseMessage
from langchain_core.runnables.base import RunnableSerializable

StructuredOutputRunnable = RunnableSerializable[list[BaseMessage], dict[str, object]]

__all__ = ["StructuredOutputRunnable"]
