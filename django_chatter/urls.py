# coding: utf-8
from django_chatter.compat import path
from . import views

# Defined namespace for use on all templates
app_name = 'django_chatter'

urlpatterns = [
    path('^$', views.IndexView.as_view(), name="index"),
    path('room/(?P<uuid>.+)/$', views.ChatRoomView.as_view(), name="chatroom"),

    # AJAX paths
    path('ajax/users-list/', views.users_list, name="users_list"),
    path('ajax/get-chat-url/', views.ChatUrlView.as_view(), name="get_chat_url"),
    path('ajax/get-messages/(?P<uuid>.+)/$', views.get_messages, name="get_messages")
]
