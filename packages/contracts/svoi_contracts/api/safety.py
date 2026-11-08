"""Safety domain: captcha (S11)."""

from pydantic import StrictStr

from svoi_contracts.base import Contract


class CaptchaChallenge(Contract):
    """Emoji captcha."""

    challenge_id: str
    target_emoji: str
    options: list[str]  # CAPTCHA_OPTIONS emoji in random order


class CaptchaAnswerIn(Contract):
    """Body of POST /users/me/captcha/verify."""

    challenge_id: StrictStr
    answer: StrictStr
