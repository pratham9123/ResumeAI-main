"""Public API error boundaries for the resume-analysis service."""


class FeedbackGenerationError(RuntimeError):
    """Raised when the feedback layer cannot produce any usable response."""

