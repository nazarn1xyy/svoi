"""fail_next / timeout_next shared by the fakes."""


class ClientError(Exception):
    """External service answered 5xx or broke the connection."""


class ClientTimeout(ClientError):
    """External service did not answer in time."""


class Faults:
    """Queue of injected failures for the next calls."""

    def __init__(self) -> None:
        self._next: list[ClientError] = []
        self.calls = 0

    def fail_next(self) -> None:
        """Next call raises ClientError (HTTP 500)."""
        self._next.append(ClientError("500"))

    def timeout_next(self) -> None:
        """Next call raises ClientTimeout."""
        self._next.append(ClientTimeout("timeout"))

    def hit(self) -> None:
        """Count the call and raise an injected failure, if any."""
        self.calls += 1
        if self._next:
            raise self._next.pop(0)
