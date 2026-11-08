"""Moderation domain: user reports and blocks (S10)."""

from typing import Annotated, Self

from pydantic import Field, StrictInt, StrictStr, model_validator

from svoi_contracts.base import Contract
from svoi_contracts.constants import REPORT_TEXT_MAX
from svoi_contracts.enums import ReportContext, ReportReason


class ReportIn(Contract):
    """Body of POST /reports."""

    target_id: StrictInt
    reason: ReportReason
    text: Annotated[StrictStr | None, Field(max_length=REPORT_TEXT_MAX)] = None
    context: ReportContext

    @model_validator(mode="after")
    def _check_rules(self) -> Self:
        if self.context is ReportContext.system:
            raise ValueError("system context is reserved for automatic reports")
        if self.reason is ReportReason.other and not (self.text and self.text.strip()):
            raise ValueError("reason other needs text")
        return self


class BlockIn(Contract):
    """Body of POST /blocks."""

    target_id: StrictInt
