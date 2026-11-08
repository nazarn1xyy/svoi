"""Product constants from docs/tech.md section 4. Code imports them, never hardcodes."""

from typing import Final

# Age and pools
AGE_MIN: Final = 16
AGE_MAX: Final = 99
ADULT_AGE: Final = 18  # pool = adult when age >= 18
AGE_EDIT_WINDOW_HOURS: Final = 24  # age may change once within 24 h of first entry
AGE_REJECT_COOLDOWN_DAYS: Final = 30  # after age < 16, re-entry is locked for 30 days (age_locked)
DEFAULT_AGE_RANGE_DELTA: Final = 3  # default filter: own age ±3, clipped to the pool bounds

# Profile
NAME_LEN: Final = (2, 20)
HEIGHT_CM: Final = (120, 230)
GOALS_COUNT: Final = (1, 7)
INTERESTS_COUNT: Final = (3, 15)
CUSTOM_INTEREST_LEN: Final = (2, 30)
PROMPTS_MAX: Final = 2
PROMPT_TEXT_MAX: Final = 300
MEDIA_MAX: Final = 3
CLARIFICATIONS_MAX: Final = 2

# Feed and matching
FEED_BATCH_SIZE: Final = 30
FEED_REFILL_AT: Final = 5
FEED_MIX: Final = (0.70, 0.20, 0.10)  # top / middle / exploration
INACTIVE_CUTOFF_DAYS: Final = 14
SKIP_REPEAT_DAYS: Final = 30
NEWBIE_BOOST: Final = 0.10
NEWBIE_BOOST_HOURS: Final = 48
SCORE_WEIGHTS: Final = {
    "interests": 0.35,
    "geo": 0.20,
    "goals": 0.15,
    "institution": 0.10,
    "activity": 0.10,
    "age": 0.05,
    "quality": 0.05,
}
GEO_WEIGHT_ONLINE_GOAL: Final = 0.05  # when both have the gaming goal and radius = any_online
CATEGORY_PARTIAL_MATCH: Final = 0.30  # same category, different tags
SAME_INSTITUTION_TYPE_SCORE: Final = 0.30
AGE_SCORE_SPAN_YEARS: Final = 5
ACTIVITY_SCORE: Final = {24: 1.0, 72: 0.6, 168: 0.3}  # hours since last activity → score

# Reactions and limits
REACTIONS_PER_DAY: Final = 100
MESSAGES_PER_DAY: Final = 20
LIKE_MESSAGE_MAX: Final = 300
LIKE_MEDIA_MAX_SECONDS: Final = 30
UNDO_WINDOW_SECONDS: Final = 60
RAPID_REACTION_INTERVAL_S: Final = 1.0
RAPID_REACTION_STREAK_S: Final = 60  # reactions faster than 1 per second for 60 s → suspicious
LIMITS_RESET_TZ: Final = "Europe/Kyiv"  # limits reset at 00:00 Kyiv time

# Likes
LIKE_EXPIRE_DAYS: Final = 14

# Safety and moderation
REPORTS_AUTOHIDE: Final = 3  # reports from distinct users → auto-hide
REPORT_TEXT_MAX: Final = 500
RISK_CAPTCHA_THRESHOLD: Final = 50  # risk_score ≥ 50 → captcha
CAPTCHA_OPTIONS: Final = 6
CAPTCHA_TTL_SECONDS: Final = 300
DUP_MESSAGE_THRESHOLD: Final = 5  # same message to 5+ people a day → shadow ban
NSFW_REJECT: Final = 0.85  # score ≥ → photo rejected automatically
NSFW_REVIEW: Final = 0.50  # score in [REVIEW, REJECT) → manual photos queue
PHASH_DUP_DISTANCE: Final = 6  # Hamming distance ≤ → duplicate photo from another account
FAST_ONBOARDING_SECONDS: Final = 40  # faster onboarding → more risk
CAPTCHA_FAILS_RISK: Final = 3  # 3 captcha failures in a row → +10 risk
OUTBOX_REENQUEUE_MINUTES: Final = 30
OUTBOX_MAX_ATTEMPTS: Final = 3
GEO_ROUND_DECIMALS: Final = 2  # ~1 km
DISTANCE_BUCKETS_KM: Final = (5, 25, 100)

# Notifications
QUIET_HOURS_DEFAULT: Final = ("23:00", "08:00")
REMINDER_DAYS: Final = (3, 7)
NEW_PEOPLE_DIGEST_PER_DAY: Final = 1
NEW_PEOPLE_MIN: Final = 3  # digest only when ≥ 3 new people share an interest
DAILY_DIGEST_HOUR: Final = 19  # daily frequency → 19:00 in the user's tz

# Referrals
REFERRAL_BONUS_REACTIONS: Final = 20
