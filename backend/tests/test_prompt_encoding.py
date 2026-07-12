import unittest

from backend.agents.nodes.comment_compose import _load_prompt as load_comment_prompt
from backend.agents.nodes.issue_detection import _load_prompt as load_issue_prompt
from backend.agents.nodes.risk_analysis import _load_prompt as load_risk_prompt
from backend.agents.nodes.summary import _load_prompt as load_summary_prompt
from backend.agents.nodes.test_suggestions import _load_prompt as load_test_prompt


class PromptEncodingTests(unittest.TestCase):
    def test_prompt_templates_load_as_utf8(self):
        loaders = [
            lambda: load_summary_prompt("项目描述", "diff --git a/a.py b/a.py"),
            lambda: load_risk_prompt("项目描述", "摘要", "diff --git a/a.py b/a.py"),
            lambda: load_issue_prompt("项目描述", "摘要", "diff --git a/a.py b/a.py"),
            lambda: load_test_prompt("项目描述", "摘要", "diff --git a/a.py b/a.py"),
            lambda: load_comment_prompt("项目描述", "摘要", "审查报告"),
        ]

        for load_prompt in loaders:
            _, user_prompt = load_prompt()
            self.assertIn("项目描述", user_prompt)


if __name__ == "__main__":
    unittest.main()
