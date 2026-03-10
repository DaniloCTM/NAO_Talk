"""Abstract base class for Text-to-Speech backends."""


class BaseTTS:
    """Interface that all TTS implementations must satisfy."""

    def speak(self, text: str) -> None:
        """Convert text to speech and play it.

        Args:
            text: Text to be synthesised and spoken aloud.
        """
        raise NotImplementedError
