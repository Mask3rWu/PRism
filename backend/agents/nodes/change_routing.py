from backend.agents.routing import build_routing_plan
from backend.agents.states import ReviewState


async def analyze_changes_node(state: ReviewState) -> dict:
    plan = build_routing_plan(
        state.get("pr_diff", ""),
        state.get("enabled_agents"),
        state.get("project_description", ""),
    )
    return {"routing_plan": plan, "selected_agents": plan["selected_agents"]}
