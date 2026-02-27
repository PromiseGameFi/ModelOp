import unittest

from modelop.context_window import ContextWindowOptimizer


class ContextWindowOptimizerTests(unittest.TestCase):
    def test_returns_prompt_unchanged_when_within_budget(self) -> None:
        optimizer = ContextWindowOptimizer()
        prompt = "short prompt"

        result = optimizer.optimize(prompt=prompt, max_prompt_tokens=20)

        self.assertFalse(result.prompt_truncated)
        self.assertEqual(result.prompt, prompt)
        self.assertEqual(result.original_prompt_tokens, result.effective_prompt_tokens)

    def test_truncates_prompt_when_over_budget(self) -> None:
        optimizer = ContextWindowOptimizer()
        prompt = "A" * 400

        result = optimizer.optimize(prompt=prompt, max_prompt_tokens=20)

        self.assertTrue(result.prompt_truncated)
        self.assertLessEqual(result.effective_prompt_tokens, 20)
        self.assertIn("[...context truncated...]", result.prompt)
