import asyncio
import unittest
from unittest.mock import AsyncMock, patch

from backend.agents.nodes.expert_review import (
    _build_prompt,
    _shared_prompt_prefix,
    expert_cache_warmup_node,
)


class ExpertCacheWarmupTests(unittest.TestCase):
    def test_expert_prompts_share_an_identical_prefix(self):
        project = "project"
        summary = {"overview": "summary"}
        common = {"fact": "common"}
        diff = "diff"
        prefix = _shared_prompt_prefix(project, summary, common, diff)
        _, issue_prompt = _build_prompt("issue_detection", project, summary, common, {"issue": True}, diff)
        _, risk_prompt = _build_prompt("risk_analysis", project, summary, common, {"risk": True}, diff)
        self.assertTrue(issue_prompt.startswith(prefix))
        self.assertTrue(risk_prompt.startswith(prefix))

    def test_expert_cache_warmup_uses_one_output_token(self):
        state = {
            "selected_agents": ["issue_detection"],
            "project_description": "project",
            "summary_result": {"overview": "summary"},
            "common_context": {"fact": "common"},
            "pr_diff": "diff",
        }
        with patch("backend.agents.nodes.expert_review.llm_call", new_callable=AsyncMock) as call:
            asyncio.run(expert_cache_warmup_node(state))
        call.assert_awaited_once()
        self.assertEqual(call.await_args.kwargs["max_tokens"], 1)
        self.assertEqual(call.await_args.kwargs["observation_metadata"]["purpose"], "expert_cache_warmup")


if __name__ == "__main__":
    unittest.main()
