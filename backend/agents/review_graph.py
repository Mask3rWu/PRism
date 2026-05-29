from langgraph.graph import END, START, StateGraph
from langgraph.graph.state import CompiledStateGraph

from backend.agents.nodes.comment_compose import comment_compose_node
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
    builder.add_node("comment_compose", comment_compose_node)  # type: ignore[arg-type]

    builder.add_edge(START, "summary")
    builder.add_edge("summary", "risk_analysis")
    builder.add_edge("summary", "issue_detection")
    builder.add_edge("summary", "test_suggestions")
    builder.add_edge("risk_analysis", "comment_compose")
    builder.add_edge("issue_detection", "comment_compose")
    builder.add_edge("test_suggestions", "comment_compose")
    builder.add_edge("comment_compose", END)

    return builder.compile()


review_graph = build_review_graph()
