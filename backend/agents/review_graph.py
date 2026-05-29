from langgraph.graph import END, START, StateGraph
from langgraph.graph.state import CompiledStateGraph

from backend.agents.nodes.risk_analysis import risk_analysis_node
from backend.agents.nodes.summary import summary_node
from backend.agents.states import ReviewState


def build_review_graph() -> CompiledStateGraph[ReviewState, None, ReviewState, ReviewState]:
    builder = StateGraph(ReviewState)

    builder.add_node("summary", summary_node)  # type: ignore[arg-type]
    builder.add_node("risk_analysis", risk_analysis_node)  # type: ignore[arg-type]

    builder.add_edge(START, "summary")
    builder.add_edge("summary", "risk_analysis")
    builder.add_edge("risk_analysis", END)

    return builder.compile()


review_graph = build_review_graph()
