from django.db import models
from user_app.models import CustomUser
from booking_app.models import Booking


class ChatMessage(models.Model):
    message = models.TextField()
    timestamp = models.DateTimeField(auto_now_add=True)
    booking = models.ForeignKey(Booking, on_delete=models.CASCADE)
    sender = models.ForeignKey(CustomUser, on_delete=models.CASCADE)

    class Meta:
        db_table = 'chat_chatmessage'
        ordering = ['timestamp']
    # Let Django manage the chat table (create migrations & migrate) so it is
    # tracked by migrations. If your production DB already has the table and
    # you don't want Django to alter it, set managed = False instead.
    managed = True

    def __str__(self):
        return f"Message {self.id} for Booking {self.booking_id} by {self.sender.username}"
