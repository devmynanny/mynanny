# Write-side vocabularies for the chat-messaging feature (conversations,
# messages, per-user channel preference). Mirrors the pattern in
# booking_status.py: these are the single source of truth, enforced via
# @validates hooks on the models.

CONVERSATION_CHANNELS = frozenset({"whatsapp", "telegram"})

MESSAGE_DIRECTIONS = frozenset({"inbound", "outbound"})

MESSAGE_STATUSES = frozenset({"received", "sent", "failed"})

PREFERRED_MESSAGING_CHANNELS = frozenset({"whatsapp", "telegram", "email", "sms"})
