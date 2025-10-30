from channels.generic.websocket import AsyncWebsocketConsumer
import json
from channels.db import database_sync_to_async
from .models import ChatMessage
from django.contrib.auth import get_user_model

User = get_user_model()


class ChatConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        # Expect booking_id in the URL route kwargs
        self.booking_id = self.scope['url_route']['kwargs'].get('booking_id')
        self.group_name = f'chat_{self.booking_id}'

        # Only allow authenticated users
        user = self.scope.get('user')
        if not user or not user.is_authenticated:
            await self.close()
            return

        await self.channel_layer.group_add(self.group_name, self.channel_name)
        await self.accept()

    async def disconnect(self, close_code):
        await self.channel_layer.group_discard(self.group_name, self.channel_name)

    async def receive(self, text_data=None, bytes_data=None):
        if text_data is None:
            return
        try:
            payload = json.loads(text_data)
            message = payload.get('message')
            if not message:
                return
            user = self.scope.get('user')

            # Save message to DB
            chat_obj = await database_sync_to_async(self._save_message)(user.id, self.booking_id, message)

            # Broadcast to group
            await self.channel_layer.group_send(
                self.group_name,
                {
                    'type': 'chat.message',
                    'message': message,
                    'sender': user.username,
                    'timestamp': str(chat_obj.timestamp)
                }
            )
        except Exception:
            # Ignore malformed messages
            return

    async def chat_message(self, event):
        # Send message to WebSocket
        await self.send(text_data=json.dumps({
            'message': event['message'],
            'sender': event['sender'],
            'timestamp': event['timestamp']
        }))

    def _save_message(self, user_id, booking_id, message):
        try:
            user = User.objects.get(id=user_id)
            chat = ChatMessage.objects.create(message=message, booking_id=booking_id, sender=user)
            return chat
        except Exception:
            return None
