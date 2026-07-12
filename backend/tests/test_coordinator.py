import asyncio
import unittest

from backend.agents.nodes.coordinator import (
    FINALIZER_MAX_TOOL_CONTEXT_CHARS,
    FINALIZER_MAX_TOOL_RESULTS,
    _build_finalizer_prompt,
    _build_finalizer_tool_results,
    _normalise_result,
    build_fallback_coordinator_result,
)
from backend.agents.review_graph import dispatch_selected_experts
from backend.agents.tools.context import ReviewContextTools, _safe_path
from backend.agents.tools.change_inventory import build_change_inventory, compact_inventory, is_docs_only
from backend.schemas.coordinator import (
    CommonContext,
    CoordinatorResult,
    CoordinatorRoutingPlan,
    ExpertContext,
    PrSummary,
)


class ChangeInventoryTests(unittest.TestCase):
    def test_inventory_tracks_added_modified_and_deleted_files(self):
        diff = """diff --git a/app/old.py b/app/old.py
deleted file mode 100644
--- a/app/old.py
+++ /dev/null
@@ -1,2 +0,0 @@
-old = True
-unused = True
diff --git a/app/new.py b/app/new.py
new file mode 100644
--- /dev/null
+++ b/app/new.py
@@ -0,0 +1,2 @@
+new = True
+active = True
"""
        inventory = build_change_inventory(diff)

        self.assertEqual(inventory["changed_file_count"], 2)
        self.assertEqual(inventory["files"][0]["path"], "app/old.py")
        self.assertEqual(inventory["files"][0]["status"], "deleted")
        self.assertEqual(inventory["files"][1]["path"], "app/new.py")
        self.assertEqual(inventory["files"][1]["status"], "added")
        self.assertEqual(inventory["total_additions"], 2)
        self.assertEqual(inventory["total_deletions"], 2)
        self.assertNotIn("patch", compact_inventory(inventory)["files"][0])

    def test_docs_only_inventory_recognises_extensions_and_readme(self):
        diff = """diff --git a/README b/README
--- a/README
+++ b/README
@@ -1 +1 @@
-Old command
+New command
diff --git a/docs/api.rst b/docs/api.rst
--- a/docs/api.rst
+++ b/docs/api.rst
@@ -1 +1 @@
-Old API
+New API
"""

        self.assertTrue(is_docs_only(build_change_inventory(diff)))


class CoordinatorContractTests(unittest.TestCase):
    def test_fallback_routes_core_agents_and_keeps_diff_evidence(self):
        diff = """diff --git a/app/service.py b/app/service.py
--- a/app/service.py
+++ b/app/service.py
@@ -1 +1 @@
-return False
+return True
"""
        result = build_fallback_coordinator_result(
            "A service project",
            build_change_inventory(diff),
            ["issue_detection", "test_suggestions", "security_review"],
            "Tool calling unavailable",
        )

        self.assertTrue(result.routing_plan.fallback_used)
        self.assertEqual(result.routing_plan.selected_agents, ["issue_detection", "test_suggestions"])
        self.assertEqual(result.common_context.evidence[0].path, "app/service.py")
        self.assertEqual(set(result.expert_contexts), set(result.routing_plan.selected_agents))

    def test_docs_only_fallback_routes_documentation_review(self):
        diff = """diff --git a/docs/usage.md b/docs/usage.md
--- a/docs/usage.md
+++ b/docs/usage.md
@@ -1 +1 @@
-prism review 1
+prism review 2
"""
        result = build_fallback_coordinator_result(
            "A service project",
            build_change_inventory(diff),
            ["docs_review", "general_review"],
            "Tool calling unavailable",
        )

        self.assertEqual(result.routing_plan.selected_agents, ["docs_review"])
        self.assertIn("docs_review", result.expert_contexts)

    def test_unknown_file_fallback_routes_general_review(self):
        diff = """diff --git a/Dockerfile b/Dockerfile
--- a/Dockerfile
+++ b/Dockerfile
@@ -1 +1 @@
-FROM python:3.12
+FROM python:3.13
"""
        result = build_fallback_coordinator_result(
            "A service project",
            build_change_inventory(diff),
            ["general_review", "issue_detection"],
            "Tool calling unavailable",
        )

        self.assertEqual(result.routing_plan.selected_agents, ["general_review"])

    def test_schema_rejects_context_for_unselected_agent(self):
        payload = {
            "pr_summary": {"overview": "摘要", "scope": [], "key_changes": []},
            "common_context": {"change_intent": "变更", "changed_files": []},
            "routing_plan": {"selected_agents": ["issue_detection"]},
            "expert_contexts": {"security_review": {}},
        }

        with self.assertRaises(ValueError):
            CoordinatorResult.model_validate(payload)

    def test_normalisation_covers_unassigned_changed_files(self):
        diff = """diff --git a/app/auth.py b/app/auth.py
--- a/app/auth.py
+++ b/app/auth.py
@@ -1 +1 @@
-old_auth()
+new_auth()
diff --git a/app/config.py b/app/config.py
--- a/app/config.py
+++ b/app/config.py
@@ -1 +1 @@
-enabled = False
+enabled = True
"""
        result = CoordinatorResult(
            pr_summary=PrSummary(overview="摘要"),
            common_context=CommonContext(change_intent="认证逻辑变更"),
            routing_plan=CoordinatorRoutingPlan(selected_agents=["security_review"]),
            expert_contexts={"security_review": ExpertContext(relevant_files=["app/auth.py"])},
        )

        normalised = _normalise_result(
            result,
            ["security_review"],
            build_change_inventory(diff),
            [{"tool": "get_change_inventory", "success": True, "result_chars": 1}],
            "",
            diff,
        )

        self.assertEqual(normalised.common_context.changed_files, ["app/auth.py", "app/config.py"])
        self.assertIn("app/config.py", normalised.expert_contexts["security_review"].relevant_files)
        self.assertTrue(normalised.common_context.evidence)

    def test_normalisation_preserves_documentation_expert_context(self):
        diff = """diff --git a/docs/api.md b/docs/api.md
--- a/docs/api.md
+++ b/docs/api.md
@@ -1 +1 @@
-GET /v1/items
+GET /v2/items
"""
        result = CoordinatorResult(
            pr_summary=PrSummary(overview="摘要"),
            common_context=CommonContext(change_intent="更新 API 文档"),
            routing_plan=CoordinatorRoutingPlan(selected_agents=["issue_detection"]),
            expert_contexts={"issue_detection": ExpertContext(relevant_files=["docs/api.md"])},
        )

        normalised = _normalise_result(
            result,
            ["issue_detection", "docs_review", "general_review"],
            build_change_inventory(diff),
            [],
            "",
            diff,
        )

        self.assertEqual(normalised.routing_plan.selected_agents, ["issue_detection", "docs_review"])
        self.assertIn("docs_review", normalised.expert_contexts)


class ContextToolSafetyTests(unittest.TestCase):
    def test_paths_cannot_escape_repository_scope(self):
        for path in ("../.env", "/etc/passwd", "src/file.py?ref=other", "src:file.py"):
            with self.assertRaises(ValueError):
                _safe_path(path)

    def test_change_inventory_tool_returns_bounded_hunks(self):
        diff = """diff --git a/app/service.py b/app/service.py
--- a/app/service.py
+++ b/app/service.py
@@ -1 +1 @@
-old()
+new()
"""
        tools = ReviewContextTools("owner", "repo", 1, "", diff)
        result = asyncio.run(tools.get_change_inventory())

        self.assertEqual(result["files"][0]["path"], "app/service.py")
        self.assertIn("get_change_inventory", [call["tool"] for call in tools.tool_summary])

    def test_search_rejects_scope_override_before_network_access(self):
        tools = ReviewContextTools("owner", "repo", 1, "", "")

        with self.assertRaises(ValueError):
            asyncio.run(tools.search_repository("token repo:another/repo"))


class FinalizerContextTests(unittest.TestCase):
    def test_finalizer_receives_only_bounded_tool_messages(self):
        ToolMessage = type("ToolMessage", (), {})
        AIMessage = type("AIMessage", (), {})
        messages = []
        for index in range(FINALIZER_MAX_TOOL_RESULTS + 3):
            message = ToolMessage()
            message.name = f"tool_{index}"
            message.content = "x" * 10_000
            messages.append(message)
        ignored = AIMessage()
        ignored.name = "model"
        ignored.content = "model reasoning must not be forwarded"
        messages.insert(0, ignored)

        results = _build_finalizer_tool_results(messages)

        self.assertLessEqual(len(results), FINALIZER_MAX_TOOL_RESULTS)
        self.assertGreater(len(results), 0)
        self.assertLessEqual(
            sum(len(result["result"]) for result in results),
            FINALIZER_MAX_TOOL_CONTEXT_CHARS,
        )
        self.assertNotIn("model reasoning", str(results))

    def test_finalizer_catalog_includes_documentation_and_reserves_general_review(self):
        prompt = _build_finalizer_prompt(
            "",
            {"files": [], "changed_file_count": 0, "total_additions": 0, "total_deletions": 0},
            ["docs_review", "general_review"],
            [],
        )

        self.assertIn('"key": "docs_review"', prompt)
        self.assertIn("documentation accuracy", prompt)
        self.assertNotIn('"key": "general_review"', prompt)
        self.assertIn("`general_review` is reserved for deterministic fallback", prompt)


class CoordinatorDispatchTests(unittest.TestCase):
    def test_dispatches_only_selected_agents(self):
        sends = dispatch_selected_experts({"selected_agents": ["security_review", "performance_review"]})

        self.assertEqual(len(sends), 2)
        self.assertTrue(all(send.node == "review_expert" for send in sends))
        self.assertEqual({send.arg["active_expert"] for send in sends}, {"security_review", "performance_review"})

    def test_empty_selection_goes_to_aggregation(self):
        self.assertEqual(dispatch_selected_experts({"selected_agents": []}), "aggregate_results")


if __name__ == "__main__":
    unittest.main()
