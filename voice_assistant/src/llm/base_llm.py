"""Abstract base class for LLM backends."""


class BaseLLM:
    """Interface that all LLM implementations must satisfy."""

    def generate(self, prompt: str, conversation_id: str | None = None) -> str:
        """Generate a text response for the given prompt.

        Args:
            prompt: User input text.
            conversation_id: Optional session identifier for conversation memory.

        Returns:
            Model-generated response string.
        """
        raise NotImplementedError
