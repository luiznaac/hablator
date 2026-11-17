"""SQL CHECK expressions shared by entities. Migrations keep their own frozen copies."""

from __future__ import annotations

CHANNEL_CHECK = "channel IN ('email', 'push', 'sms', 'voice')"
