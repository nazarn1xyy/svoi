"""Referrals domain (S14)."""

from svoi_contracts.base import Contract


class ReferralOut(Contract):
    """Referral code and stats."""

    code: str  # the bot builds https://t.me/<bot>?start=r_<code>
    invited_count: int
    bonus_per_invite: int  # REFERRAL_BONUS_REACTIONS
