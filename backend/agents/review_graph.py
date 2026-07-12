from langgraph.graph import END, START, StateGraph
from langgraph.graph.state import CompiledStateGraph
from langgraph.types import Send

from backend.agents.nodes.aggregate_results import aggregate_results_node
from backend.agents.nodes.change_routing import analyze_changes_node
from backend.agents.nodes.comment_compose import comment_compose_node
from backend.agents.nodes.expert_review import expert_review_node
from backend.agents.nodes.summary import summary_node
from backend.agents.states import ReviewState
from backend.core.observability import observe_graph_node, update_observation


def route_to_experts(state: ReviewState) -> list[Send] | str:
    selected_agents = state.get("selected_agents", [])
    if not selected_agents:
        return "aggregate_results"
    return [Send("review_expert", {**state, "active_expert": agent}) for agent in selected_agents]


def observed_node(node_name: str, node):
    """Attach one Langfuse Agent observation to every graph node."""
    async def wrapped(state: ReviewState) -> dict:
        with observe_graph_node(node_name, state) as observation:
            try:
                result = await node(state)
                update_observation(observation, output=result)
                return result
            except Exception as exc:
                update_observation(
                    observation,
                    level="ERROR",
                    status_message=str(exc),
                )
                raise

    return wrapped


def build_review_graph() -> CompiledStateGraph[ReviewState, None, ReviewState, ReviewState]:
    builder = StateGraph(ReviewState)

    builder.add_node("summary", observed_node("summary", summary_node))  # type: ignore[arg-type]
    builder.add_node("analyze_changes", observed_node("analyze_changes", analyze_changes_node))  # type: ignore[arg-type]
    builder.add_node("review_expert", observed_node("review_expert", expert_review_node))  # type: ignore[arg-type]
    builder.add_node("aggregate_results", observed_node("aggregate_results", aggregate_results_node))  # type: ignore[arg-type]
    builder.add_node("comment_compose", observed_node("comment_compose", comment_compose_node))  # type: ignore[arg-type]

    builder.add_edge(START, "summary")
    builder.add_edge("summary", "analyze_changes")
    builder.add_conditional_edges("analyze_changes", route_to_experts)
    builder.add_edge("review_expert", "aggregate_results")
    builder.add_edge("aggregate_results", "comment_compose")
    builder.add_edge("comment_compose", END)

    return builder.compile()


review_graph = build_review_graph()
