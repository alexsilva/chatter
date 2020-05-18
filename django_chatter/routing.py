# coding: utf-8
from django_chatter.compat import path

from . import consumers

websocket_urlpatterns = [
    path(r'ws/django_chatter/chatrooms/(?P<room_uuid>.+)/$', consumers.ChatConsumer),
    path(r'ws/django_chatter/users/(?P<user_id>\d+)/$', consumers.AlertConsumer)
]
