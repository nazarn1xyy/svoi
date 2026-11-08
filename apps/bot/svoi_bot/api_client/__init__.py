"""API client for the bot: protocol, HTTP implementation and in-memory fake."""

from svoi_bot.api_client.base import OPS, ApiClient, Op
from svoi_bot.api_client.errors import ApiException, ApiTimeout, ContractViolation
from svoi_bot.api_client.fake import Call, FakeApiClient
from svoi_bot.api_client.http import HttpApiClient

__all__ = [
    "OPS",
    "ApiClient",
    "ApiException",
    "ApiTimeout",
    "Call",
    "ContractViolation",
    "FakeApiClient",
    "HttpApiClient",
    "Op",
]
