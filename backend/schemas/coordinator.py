from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field, model_validator


class Evidence(BaseModel):
    """A repository fact that can be shown to an expert without re-retrieval."""

    source_type: Literal["pr_diff", "repository_file", "pr_metadata", "project_description"]
    path: str = ""
    ref: str = ""
    start_line: int = Field(default=0, ge=0)
    end_line: int = Field(default=0, ge=0)
    excerpt: str = Field(default="", max_length=6000)
    fact: str = Field(min_length=1, max_length=1200)


class PrSummary(BaseModel):
    overview: str = Field(min_length=1, max_length=2000)
    scope: list[str] = Field(default_factory=list, max_length=30)
    key_changes: list[str] = Field(default_factory=list, max_length=30)


class CommonContext(BaseModel):
    change_intent: str = Field(min_length=1, max_length=3000)
    affected_components: list[str] = Field(default_factory=list, max_length=50)
    behavior_before_after: list[str] = Field(default_factory=list, max_length=50)
    changed_files: list[str] = Field(default_factory=list, max_length=500)
    known_unknowns: list[str] = Field(default_factory=list, max_length=50)
    evidence: list[Evidence] = Field(default_factory=list, max_length=100)


class ExpertContext(BaseModel):
    relevant_changes: list[str] = Field(default_factory=list, max_length=50)
    relevant_files: list[str] = Field(default_factory=list, max_length=100)
    related_symbols: list[str] = Field(default_factory=list, max_length=100)
    related_tests: list[str] = Field(default_factory=list, max_length=100)
    evidence: list[Evidence] = Field(default_factory=list, max_length=100)
    unresolved_context: list[str] = Field(default_factory=list, max_length=50)


class CoordinatorRoutingPlan(BaseModel):
    selected_agents: list[str] = Field(default_factory=list, max_length=20)
    reasons: dict[str, list[str]] = Field(default_factory=dict)
    unselected_agents: dict[str, list[str]] = Field(default_factory=dict)
    fallback_used: bool = False
    fallback_reason: str = ""


class CoordinatorResult(BaseModel):
    pr_summary: PrSummary
    common_context: CommonContext
    routing_plan: CoordinatorRoutingPlan
    expert_contexts: dict[str, ExpertContext] = Field(default_factory=dict)

    @model_validator(mode="after")
    def contexts_only_exist_for_selected_agents(self) -> "CoordinatorResult":
        selected = set(self.routing_plan.selected_agents)
        extra = set(self.expert_contexts) - selected
        if extra:
            raise ValueError(f"expert_contexts contains unselected agents: {', '.join(sorted(extra))}")
        return self
