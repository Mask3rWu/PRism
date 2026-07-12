import unittest
from operator import add
from typing import Annotated

from backend.agents.nodes.aggregate_results import build_final_report
from backend.agents.routing import build_routing_plan, validate_enabled_agents
from langgraph.graph import END, START, StateGraph
from langgraph.types import Send
from typing_extensions import TypedDict


class DynamicRoutingTests(unittest.TestCase):
    def test_routes_domain_experts_from_diff_signals(self):
        diff = """diff --git a/app/payments.py b/app/payments.py
--- a/app/payments.py
+++ b/app/payments.py
@@
+async def refund_order(token: str, amount: int):
+    await database.execute(\"SELECT * FROM orders\")
+    return await process_payment(token, amount)
"""

        plan = build_routing_plan(diff, None)

        self.assertIn("issue_detection", plan["selected_agents"])
        self.assertIn("test_suggestions", plan["selected_agents"])
        self.assertIn("security_review", plan["selected_agents"])
        self.assertIn("performance_review", plan["selected_agents"])
        self.assertIn("business_compliance_review", plan["selected_agents"])
        self.assertTrue(plan["reasons"]["security_review"])

    def test_respects_enabled_agent_allow_list(self):
        diff = "+++ b/app/auth.py\n+token = request.headers.get('Authorization')\n"

        plan = build_routing_plan(diff, ["security_review"])

        self.assertEqual(plan["selected_agents"], ["security_review"])

    def test_routes_documentation_changes_to_documentation_review(self):
        diff = """diff --git a/docs/cli.md b/docs/cli.md
--- a/docs/cli.md
+++ b/docs/cli.md
@@ -1 +1 @@
-prism review 1
+prism review 2
"""

        plan = build_routing_plan(diff, ["docs_review", "general_review"])

        self.assertEqual(plan["selected_agents"], ["docs_review"])

    def test_rejects_unknown_agent(self):
        with self.assertRaises(ValueError):
            validate_enabled_agents(["security_review", "unknown"])


class ResultAggregationTests(unittest.TestCase):
    def test_de_duplicates_findings_and_orders_by_severity(self):
        expert_results = [
            {
                "agent": "security_review",
                "findings": [{
                    "severity": "high",
                    "title": "Unvalidated token",
                    "reason": "A token is accepted without verification.",
                    "file": "app/auth.py",
                    "line_number": 12,
                    "fix_suggestion": "Verify the token signature.",
                    "verification": "Add an invalid-token test.",
                }],
            },
            {
                "agent": "issue_detection",
                "findings": [
                    {
                        "severity": "high",
                        "title": "Unvalidated token",
                        "reason": "Duplicate finding from a second expert.",
                        "file": "app/auth.py",
                        "line_number": 12,
                        "fix_suggestion": "Verify the token signature.",
                    },
                    {
                        "severity": "critical",
                        "title": "Secret in source",
                        "reason": "A credential is committed.",
                        "file": "app/config.py",
                        "line_number": "3",
                        "fix_suggestion": "Move it to a secret store.",
                    },
                ],
            },
        ]

        report = build_final_report({"selected_agents": ["security_review", "issue_detection"]}, expert_results)

        self.assertEqual(report["summary"]["total_findings"], 2)
        self.assertEqual(report["findings"][0]["severity"], "critical")
        self.assertEqual(len(report["fix_suggestions"]), 2)


class FanoutState(TypedDict, total=False):
    selected_agents: list[str]
    active_expert: str
    expert_results: Annotated[list[str], add]
    aggregate_calls: Annotated[int, add]


class LangGraphFanoutTests(unittest.TestCase):
    def test_parallel_sends_join_before_aggregation(self):
        builder = StateGraph(FanoutState)
        builder.add_node("route", lambda _: {})
        builder.add_node("review_expert", lambda state: {"expert_results": [state["active_expert"]]})
        builder.add_node("aggregate", lambda _: {"aggregate_calls": 1})
        builder.add_edge(START, "route")
        builder.add_conditional_edges(
            "route",
            lambda state: [Send("review_expert", {**state, "active_expert": agent}) for agent in state["selected_agents"]],
        )
        builder.add_edge("review_expert", "aggregate")
        builder.add_edge("aggregate", END)

        result = builder.compile().invoke({"selected_agents": ["security_review", "performance_review"]})

        self.assertEqual(set(result["expert_results"]), {"security_review", "performance_review"})
        self.assertEqual(result["aggregate_calls"], 1)


if __name__ == "__main__":
    unittest.main()
