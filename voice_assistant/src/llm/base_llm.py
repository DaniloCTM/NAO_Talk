"""Abstract base class for LLM backends."""


class BaseLLM:
    """Interface that all LLM implementations must satisfy."""

    def generate(self, prompt: str) -> str:
        """Generate a text response for the given prompt.

        Args:
            prompt: User input text.

        Returns:
            Model-generated response string.
        """
        raise NotImplementedError
