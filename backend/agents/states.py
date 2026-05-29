from typing import NotRequired, TypedDict


class ReviewState(TypedDict, total=False):
    review_id: NotRequired[int]
    project_description: NotRequired[str]
    pr_diff: NotRequired[str]
    summary_result: NotRequired[dict | None]
    risk_result: NotRequired[dict | None]
    issue_result: NotRequired[dict | None]
    test_result: NotRequired[dict | None]
