"""Enums from docs/tech.md section 6.1; every value equals its name."""

from enum import StrEnum


class Lang(StrEnum):
    uk = "uk"
    ru = "ru"
    en = "en"


class UserStatus(StrEnum):
    onboarding = "onboarding"
    active = "active"
    hidden = "hidden"
    banned = "banned"
    deleted = "deleted"


class OnboardingStep(StrEnum):
    lang = "lang"
    consent = "consent"
    age = "age"
    name = "name"
    gender = "gender"
    city = "city"
    goals = "goals"
    interests = "interests"
    clarify = "clarify"
    institution = "institution"
    height = "height"
    prompts = "prompts"
    media = "media"
    preview = "preview"
    done = "done"


class Gender(StrEnum):
    male = "male"
    female = "female"
    hidden = "hidden"


class Pool(StrEnum):
    minor = "minor"
    adult = "adult"


class GoalCode(StrEnum):
    friends = "friends"
    walks = "walks"
    sport = "sport"
    study = "study"
    gaming = "gaming"
    creative = "creative"
    chat = "chat"


class MediaKind(StrEnum):
    photo = "photo"
    video = "video"


class MessageMediaKind(StrEnum):
    voice = "voice"
    video_note = "video_note"


class ModerationStatus(StrEnum):
    pending = "pending"
    approved = "approved"
    rejected = "rejected"


class InstitutionType(StrEnum):
    university = "university"
    college = "college"
    other = "other"


class GenderFilter(StrEnum):
    all = "all"
    male = "male"
    female = "female"


class RadiusMode(StrEnum):
    """Region means the whole oblast of the user's city."""

    city = "city"
    km25 = "km25"
    km50 = "km50"
    km100 = "km100"
    region = "region"
    country = "country"
    any_online = "any_online"


class DistanceBucket(StrEnum):
    same_city = "same_city"
    km5 = "km5"
    km25 = "km25"
    km100 = "km100"


class NotifyFrequency(StrEnum):
    instant = "instant"
    hourly = "hourly"
    daily = "daily"


class ViewAction(StrEnum):
    shown = "shown"
    like = "like"
    like_msg = "like_msg"
    skip = "skip"
    undo = "undo"
    report = "report"
    block = "block"


class ReactionType(StrEnum):
    like = "like"
    like_msg = "like_msg"
    skip = "skip"


class LikeStatus(StrEnum):
    pending = "pending"
    matched = "matched"
    declined = "declined"
    expired = "expired"


class LikeDecision(StrEnum):
    accept = "accept"
    decline = "decline"


class ReportReason(StrEnum):
    spam = "spam"
    fake = "fake"
    nsfw = "nsfw"
    abuse = "abuse"
    underage = "underage"
    scam = "scam"
    other = "other"


class ReportContext(StrEnum):
    """System is reserved for automatic reports and forbidden in ReportIn."""

    feed = "feed"
    incoming = "incoming"
    contact = "contact"
    system = "system"


class ReportStatus(StrEnum):
    open = "open"
    accepted = "accepted"
    rejected = "rejected"


class FeedEmptyReason(StrEnum):
    no_candidates = "no_candidates"
    limit_reached = "limit_reached"
    profile_hidden = "profile_hidden"
    profile_incomplete = "profile_incomplete"
    banned = "banned"


class IcebreakerTemplate(StrEnum):
    common_interest = "common_interest"
    same_institution = "same_institution"
    common_goal = "common_goal"


class GestureCode(StrEnum):
    three_fingers = "three_fingers"
    thumb_up = "thumb_up"
    peace = "peace"
    wave = "wave"
    ok_sign = "ok_sign"
    point_up = "point_up"


class AdminQueueKind(StrEnum):
    reports = "reports"
    photos = "photos"
    verifications = "verifications"
    custom_tags = "custom_tags"
    texts = "texts"


class AdminAction(StrEnum):
    ok = "ok"
    delete_media = "delete_media"
    delete_text = "delete_text"
    ban_7d = "ban_7d"
    ban_forever = "ban_forever"
    move_to_minor_pool = "move_to_minor_pool"
    approve = "approve"
    reject = "reject"


class NotificationKind(StrEnum):
    likes = "likes"
    match = "match"
    reminder = "reminder"
    new_people = "new_people"
    moderation = "moderation"


class ReminderKind(StrEnum):
    day3 = "day3"
    day7 = "day7"


class ModerationResultKind(StrEnum):
    media_rejected = "media_rejected"
    text_removed = "text_removed"
    banned = "banned"
    unbanned = "unbanned"
    verified = "verified"
    verification_rejected = "verification_rejected"
    tag_approved = "tag_approved"
    tag_rejected = "tag_rejected"


class OutboxStatus(StrEnum):
    pending = "pending"
    enqueued = "enqueued"
    sent = "sent"
    failed = "failed"
    cancelled = "cancelled"


class BonusSource(StrEnum):
    referral = "referral"
    admin = "admin"


class RebuildReason(StrEnum):
    filters_changed = "filters_changed"
    profile_changed = "profile_changed"
    expand = "expand"
    refill = "refill"
    daily = "daily"


class RiskLevel(StrEnum):
    low = "low"
    high = "high"


class ContentField(StrEnum):
    name = "name"
    prompt = "prompt"
    like_message = "like_message"
    custom_interest = "custom_interest"
    report_text = "report_text"


class ContentBlockReason(StrEnum):
    link = "link"
    mention = "mention"
    phone = "phone"
    stopword = "stopword"
    age_mismatch = "age_mismatch"
