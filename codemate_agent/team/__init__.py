"""
Team runtime utilities.

提供团队通信、协议追踪、任务板与结构化事件日志能力。
"""

from .event_log import StructuredEventLogger
from .message_bus import MessageBus
from .definitions import TeamMember, TeamDefinition, ExecutionRequest, ExecutionResult
from .team_defaults import get_default_team_definition
from .executor import AgentExecutor
from .coordinator import StrictWorkflowError, TeamCoordinator
from .queue import DispatchQueue
from .protocols import (
    VALID_MESSAGE_TYPES,
    RequestRecord,
    RequestTracker,
    TeamMessage,
)
from .task_board import TaskBoard

__all__ = [
    "StructuredEventLogger",
    "MessageBus",
    "TaskBoard",
    "TeamMember",
    "TeamDefinition",
    "ExecutionRequest",
    "ExecutionResult",
    "get_default_team_definition",
    "AgentExecutor",
    "TeamCoordinator",
    "StrictWorkflowError",
    "DispatchQueue",
    "TeamMessage",
    "RequestRecord",
    "RequestTracker",
    "VALID_MESSAGE_TYPES",
]
