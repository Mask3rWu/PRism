from operator import add
from typing import Annotated, NotRequired, TypedDict


class ReviewState(TypedDict, total=False):
    review_id: NotRequired[int]
    project_description: NotRequired[str]
    pr_diff: NotRequired[str]
    summary_result: NotRequired[dict | None]
    risk_result: NotRequired[dict | None]
    issue_result: NotRequired[dict | None]
    test_result: NotRequired[dict | None]
    comment_result: NotRequired[dict | None]
    routing_plan: NotRequired[dict]
    selected_agents: NotRequired[list[str]]
    active_expert: NotRequired[str]
    expert_results: Annotated[list[dict], add]
    final_report: NotRequired[dict | None]
    enabled_agents: NotRequired[list[str]]
    write_comment: NotRequired[bool]
