from typing import Annotated, TypedDict
from langchain_core.messages import AnyMessage
from langgraph.graph.message import add_messages

merge_messages=add_messages

def merge_evidence(previous,updates):return list(dict.fromkeys((previous or [])+(updates or [])))

class AgentState(TypedDict,total=False):
    messages: Annotated[list[AnyMessage],merge_messages]
    evidence_ids: Annotated[list[str],merge_evidence]
    refinement_base: dict
    refinement_request: str
    plan: dict
    proposal_generation: int
    candidate_id: str | None
    review_state: dict
    memory_ids: list[str]
    memory_versions: dict[str,str]
    run_id: str
    thread_id: str
    budget_reference: str
    model_calls: int
    tool_calls: int
    repair_count: int
    active_seconds: float
    cancelled: bool
    clarification: str | None
