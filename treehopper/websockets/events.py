from typing import TypedDict, Literal, List
from treehopper.th_config import EventType


class BaseEvent(TypedDict):
    type: EventType


class RunEvent(BaseEvent):
    run_id: str


class StepEvent(RunEvent):
    step_id: str
    step_index: int | None
    mode: Literal["sequential", "parallel"] | None


class AgentEvent(RunEvent):
    step_id: str
    agent: str


class ParallelCompleteEvent(RunEvent):
    step_id: str
    agents: List[str]


class MergeCompleteEvent(RunEvent):
    step_id: str
    merge_agent: str
    merged_keys: List[str]


class RouteTakenEvent(RunEvent):
    from_step: str
    to_step: str
    condition: str


class RunCompletedEvent(RunEvent):
    status: Literal["success", "cancelled"]
