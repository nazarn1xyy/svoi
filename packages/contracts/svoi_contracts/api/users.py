"""Users domain: start and language (S1)."""

from pydantic import StrictBool, StrictStr

from svoi_contracts.base import Contract
from svoi_contracts.enums import Lang


class StartIn(Contract):
    """Body of POST /users/start."""

    tg_username: StrictStr | None
    tg_first_name: StrictStr | None
    tg_language_code: StrictStr | None  # picks the default language
    has_tg_profile_photo: StrictBool  # feeds risk scoring
    referral_code: StrictStr | None = None  # from /start <payload>


class LangIn(Contract):
    """Body of PUT /users/me/lang."""

    lang: Lang
