# coding: utf-8
from django_chatter.compat import path

from . import consumers

websocket_urlpatterns = [
    path('ws/django_chatter/chatrooms/(?P<room_uuid>.+)/$', consumers.ChatConsumer),
    path('ws/django_chatter/users/(?P<username>.+)/$', consumers.AlertConsumer)
]
