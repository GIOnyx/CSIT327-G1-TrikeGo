from django.contrib import admin
from .models import ChatMessage


@admin.register(ChatMessage)
class ChatMessageAdmin(admin.ModelAdmin):
    list_display = ('id', 'booking', 'sender', 'timestamp')
    list_filter = ('timestamp',)
    search_fields = ('message', 'sender__username', 'booking__id')
