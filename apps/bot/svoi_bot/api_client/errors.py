"""Exceptions the bot handles around API calls."""

from svoi_contracts.errors import ApiError


class ApiException(Exception):
    """The API answered with an ApiError body."""

    def __init__(self, err: ApiError) -> None:
        super().__init__(f"{err.code}: {err.message}")
        self.err = err


class ApiTimeout(Exception):
    """The API did not answer in time or the network failed."""


class ContractViolation(Exception):
    """The bot sent a request that the contract does not allow (FakeApiClient only)."""
