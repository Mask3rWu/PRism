import unittest
from unittest.mock import patch

from backend.core import observability
from backend.core.llm_client import _extract_usage


class FakeObservation:
    def __init__(self):
        self.updates = []

    def update(self, **kwargs):
        self.updates.append(kwargs)


class FakeObservationManager:
    def __init__(self, observation):
        self.observation = observation

    def __enter__(self):
        return self.observation

    def __exit__(self, *_):
        return False


class FakeLangfuseClient:
    def __init__(self):
        self.observation = FakeObservation()
        self.calls = []

    def start_as_current_observation(self, **kwargs):
        self.calls.append(kwargs)
        return FakeObservationManager(self.observation)


class ObservabilityTests(unittest.TestCase):
    def setUp(self):
        self.trace_content = observability.settings.LANGFUSE_TRACE_CONTENT
        self.input_price = observability.settings.LANGFUSE_INPUT_COST_PER_1M_TOKENS
        self.cache_hit_price = observability.settings.LANGFUSE_CACHE_HIT_INPUT_COST_PER_1M_TOKENS
        self.cache_miss_price = observability.settings.LANGFUSE_CACHE_MISS_INPUT_COST_PER_1M_TOKENS
        self.output_price = observability.settings.LANGFUSE_OUTPUT_COST_PER_1M_TOKENS

    def tearDown(self):
        observability.settings.LANGFUSE_TRACE_CONTENT = self.trace_content
        observability.settings.LANGFUSE_INPUT_COST_PER_1M_TOKENS = self.input_price
        observability.settings.LANGFUSE_CACHE_HIT_INPUT_COST_PER_1M_TOKENS = self.cache_hit_price
        observability.settings.LANGFUSE_CACHE_MISS_INPUT_COST_PER_1M_TOKENS = self.cache_miss_price
        observability.settings.LANGFUSE_OUTPUT_COST_PER_1M_TOKENS = self.output_price

    def test_content_is_summarized_by_default(self):
        observability.settings.LANGFUSE_TRACE_CONTENT = False

        self.assertEqual(
            observability._content("private diff"),
            {"redacted": True, "type": "text", "chars": 12},
        )
        self.assertNotIn("private", str(observability._content({"diff": "private diff"})))

    def test_langchain_callbacks_require_content_tracing(self):
        observability.settings.LANGFUSE_TRACE_CONTENT = False
        with patch.object(observability, "langfuse_enabled", return_value=True), patch.object(
            observability, "get_langfuse_client"
        ) as get_client:
            self.assertEqual(observability.langchain_callbacks(), [])
        get_client.assert_not_called()

    def test_langchain_callbacks_use_initialized_client(self):
        callback = object()
        observability.settings.LANGFUSE_TRACE_CONTENT = True

        with patch.object(observability, "langfuse_enabled", return_value=True), patch.object(
            observability, "get_langfuse_client", return_value=object()
        ), patch("langfuse.langchain.CallbackHandler", return_value=callback) as handler:
            self.assertEqual(observability.langchain_callbacks(), [callback])

        handler.assert_called_once_with(public_key=observability.settings.LANGFUSE_PUBLIC_KEY)

    def test_langchain_callback_initialization_logs_and_degrades_gracefully(self):
        observability.settings.LANGFUSE_TRACE_CONTENT = True

        with patch.object(observability, "langfuse_enabled", return_value=True), patch.object(
            observability, "get_langfuse_client", return_value=object()
        ), patch("langfuse.langchain.CallbackHandler", side_effect=RuntimeError("missing dependency")):
            with self.assertLogs(observability.logger, level="ERROR") as logs:
                self.assertEqual(observability.langchain_callbacks(), [])

        self.assertIn("Failed to initialize Langfuse LangChain callback", logs.output[0])

    def test_content_is_retained_when_content_tracing_is_enabled(self):
        observability.settings.LANGFUSE_TRACE_CONTENT = True

        self.assertEqual(observability._content("private diff"), "private diff")

    def test_generation_update_preserves_usage_and_cost(self):
        observation = FakeObservation()

        observability.update_observation(
            observation,
            output="model response",
            usage_details={"prompt_tokens": 10, "completion_tokens": 5},
            cost_details={"total_cost": 0.001},
        )

        self.assertEqual(observation.updates[0]["usage_details"]["prompt_tokens"], 10)
        self.assertEqual(observation.updates[0]["cost_details"]["total_cost"], 0.001)

    def test_cost_uses_deepseek_cache_hit_and_miss_prices(self):
        observability.settings.LANGFUSE_CACHE_HIT_INPUT_COST_PER_1M_TOKENS = 1.0
        observability.settings.LANGFUSE_CACHE_MISS_INPUT_COST_PER_1M_TOKENS = 2.0
        observability.settings.LANGFUSE_OUTPUT_COST_PER_1M_TOKENS = 3.0

        cost = observability.calculate_cost_details({
            "prompt_tokens": 1200,
            "completion_tokens": 300,
            "prompt_cache_hit_tokens": 800,
            "prompt_cache_miss_tokens": 400,
        })

        self.assertEqual(cost, {"total_cost": 0.0025})

    def test_generation_uses_redacted_input_when_content_tracing_is_disabled(self):
        client = FakeLangfuseClient()
        observability.settings.LANGFUSE_TRACE_CONTENT = False

        with patch.object(observability, "get_langfuse_client", return_value=client):
            with observability.observe_llm_generation(
                "test-model",
                "https://llm.example.com/v1/chat/completions",
                "private system prompt",
                "private PR diff",
            ) as generation:
                observability.update_observation(generation, output="private model output")

        payload = str(client.calls[0]["input"])
        self.assertNotIn("private", payload)
        self.assertEqual(client.calls[0]["metadata"]["provider_host"], "llm.example.com")

    def test_extract_usage_supports_openai_and_provider_aliases(self):
        self.assertEqual(
            _extract_usage({"prompt_tokens": 12, "completion_tokens": 8, "total_tokens": 20}),
            {"prompt_tokens": 12, "completion_tokens": 8, "total_tokens": 20},
        )
        self.assertEqual(
            _extract_usage({"input_tokens": 12, "output_tokens": 8}),
            {"prompt_tokens": 12, "completion_tokens": 8, "total_tokens": 20},
        )

    def test_extract_usage_preserves_deepseek_cache_breakdown(self):
        self.assertEqual(
            _extract_usage({
                "prompt_tokens": 1200,
                "completion_tokens": 300,
                "total_tokens": 1500,
                "prompt_cache_hit_tokens": 800,
                "prompt_cache_miss_tokens": 400,
            }),
            {
                "prompt_tokens": 1200,
                "completion_tokens": 300,
                "total_tokens": 1500,
                "prompt_cache_hit_tokens": 800,
                "prompt_cache_miss_tokens": 400,
            },
        )


if __name__ == "__main__":
    unittest.main()
