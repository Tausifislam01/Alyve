from django.contrib import admin
from unfold.admin import ModelAdmin

from .models import ConversationSession, ConversationMessage


@admin.register(ConversationSession)
class ConversationSessionAdmin(ModelAdmin):
    list_display = ("id", "profile_id", "user", "loved_one", "started_at", "ended_at", "last_activity_at")
    list_filter = ("started_at", "ended_at")
    search_fields = ("profile_id", "title", "user__email", "loved_one__name")


@admin.register(ConversationMessage)
class ConversationMessageAdmin(ModelAdmin):
    list_display = ("id", "session", "seq", "role", "created_at")
    list_filter = ("role", "created_at")
    search_fields = ("content",)
