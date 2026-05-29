from langgraph.graph import END, START, StateGraph
from langgraph.graph.state import CompiledStateGraph

from backend.agents.nodes.issue_detection import issue_detection_node
from backend.agents.nodes.risk_analysis import risk_analysis_node
from backend.agents.nodes.summary import summary_node
from backend.agents.nodes.test_suggestions import test_suggestions_node
from backend.agents.states import ReviewState


def build_review_graph() -> CompiledStateGraph[ReviewState, None, ReviewState, ReviewState]:
    builder = StateGraph(ReviewState)

    builder.add_node("summary", summary_node)  # type: ignore[arg-type]
    builder.add_node("risk_analysis", risk_analysis_node)  # type: ignore[arg-type]
    builder.add_node("issue_detection", issue_detection_node)  # type: ignore[arg-type]
    builder.add_node("test_suggestions", test_suggestions_node)  # type: ignore[arg-type]

    builder.add_edge(START, "summary")
    builder.add_edge("summary", "risk_analysis")
    builder.add_edge("risk_analysis", "issue_detection")
    builder.add_edge("issue_detection", "test_suggestions")
    builder.add_edge("test_suggestions", END)

    return builder.compile()


review_graph = build_review_graph()
