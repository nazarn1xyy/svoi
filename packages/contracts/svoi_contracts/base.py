"""Base model for every contract type (docs/tech.md section 6)."""

from pydantic import BaseModel, ConfigDict


class Contract(BaseModel):
    """Frozen base that rejects unknown fields (docs/tech.md section 6)."""

    # Not strict as a whole: FastAPI validates JSON bodies in python mode, where strict models
    # reject "uk" as Lang. Request models mark their scalars Strict* instead, so the bot still
    # cannot send "19" as an age (FRONTEND S1 contract test).
    model_config = ConfigDict(extra="forbid", frozen=True)
