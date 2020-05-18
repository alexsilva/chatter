# import the logging library
import logging

from django.conf import settings
from django.contrib.auth import get_user_model
from django.contrib.auth.decorators import login_required
from django.contrib.auth.mixins import LoginRequiredMixin
from django.core.paginator import Paginator, EmptyPage, PageNotAnInteger
from django.http import HttpResponseRedirect, JsonResponse, Http404
from django.urls import reverse
from django.views import View
from django.views.generic.base import TemplateView
from django.utils.translation import gettext as _

from django_chatter.models import Room
from django_chatter.utils import create_room

# Get an instance of a logger
logger = logging.getLogger(__name__)

User = get_user_model()


def import_base_template():
    try:
        return settings.CHATTER_BASE_TEMPLATE
    except AttributeError as e:
        try:
            if settings.CHATTER_DEBUG:
                logger.info("django_chatter.views: "
                            "(Optional) settings.CHATTER_BASE_TEMPLATE not found. You can "
                            "set it to point to your base template in your settings file.")
        except AttributeError as e:
            logger.info("django_chatter.views: "
                        "(Optional) settings.CHATTER_BASE_TEMPLATE not found. You can "
                        "set it to point to your base template in your settings file.")
            logger.info("django_chatter.views: to turn off this message, set "
                        "your settings.CHATTER_DEBUG to False.")
        return 'django_chatter/base.html'


class IndexView(LoginRequiredMixin, View):

    def get(self, request, *args, **kwargs):
        rooms_list = Room.objects.filter(members=request.user).order_by('-date_modified')
        if rooms_list.exists():
            latest_room_uuid = rooms_list[0].pk
            return HttpResponseRedirect(
                reverse('django_chatter:chatroom', args=[latest_room_uuid])
            )
        else:
            # create room with the user themselves
            room = create_room([self.request.user])
            return HttpResponseRedirect(
                reverse('django_chatter:chatroom', args=[room.pk])
            )


class ChatRoomView(LoginRequiredMixin, TemplateView):
    """
    This fetches a chatroom given the room ID if a user diretly wants to access the chat.
    """
    template_name = 'django_chatter/chat-window.html'

    # This gets executed whenever a room exists
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        uuid = kwargs.get('uuid')
        try:
            room = Room.objects.get(pk=uuid)
        except Exception as e:
            logger.exception("\n\nException in django_chatter.views.ChatRoomView:\n")
            raise Http404(_("Sorry! What you're looking for isn't here."))
        user = self.request.user
        all_members = room.members.all()
        if all_members.filter(pk=user.pk).exists():
            latest_messages_curr_room = room.message_set.all()[:50]
            if latest_messages_curr_room.exists():
                message = latest_messages_curr_room[0]
                message.recipients.add(user)
            if all_members.count() == 1:
                room_name = _("Notes to Yourself")
            elif all_members.count() == 2:
                room_name = all_members.exclude(pk=user.pk)[0]
            else:
                room_name = room.__str__()
            context['room_uuid_json'] = kwargs.get('uuid')
            context['latest_messages_curr_room'] = latest_messages_curr_room
            context['room_name'] = room_name
            context['base_template'] = import_base_template()

            # Add rooms with unread messages
            rooms_list = Room.objects.filter(members=self.request.user) \
                             .order_by('-date_modified')[:10]
            rooms_with_unread = []
            # Go through each list of rooms and check if the last message was unread
            # and add each last message to the context
            for room in rooms_list:
                try:
                    message = room.message_set.all().order_by('-id')[0]
                except IndexError as e:
                    continue
                if self.request.user not in message.recipients.all():
                    rooms_with_unread.append(room.pk)
            context['rooms_list'] = rooms_list
            context['rooms_with_unread'] = rooms_with_unread

            return context
        else:
            raise Http404(_("Sorry! What you're looking for isn't here."))


# The following functions deal with AJAX requests

@login_required
def users_list(request):
    if request.is_ajax():
        data_array = []
        for user in User.objects.all():
            data_dict = {
                'id': user.pk,
                'text': str(user)
            }
            data_array.append(data_dict)
        return JsonResponse(data_array, safe=False)


@login_required
def get_chat_url(request):
    """
    AI-------------------------------------------------------------------
        Use the util room creation function to create room for one/two
        user(s). This can be extended in the future to add multiple users
        in a group chat.
    -------------------------------------------------------------------AI
    """

    user = request.user
    target_user = User.objects.get(pk=request.POST.get('target_user'))

    if user == target_user:
        room = create_room([user])
    else:
        room = create_room([user, target_user])
    return HttpResponseRedirect(
        reverse('django_chatter:chatroom', args=[room.pk])
    )


# Ajax request to fetch earlier messages

@login_required
def get_messages(request, uuid):
    if request.is_ajax():
        user = request.user
        room = Room.objects.get(pk=uuid)
        if room.members.filter(pk=user.pk).exists():
            messages = room.message_set.all()
            page = request.GET.get('page')

            paginator = Paginator(messages, 20)
            try:
                selected = paginator.page(page)
            except PageNotAnInteger:
                selected = paginator.page(1)
            except EmptyPage:
                selected = []
            messages_array = []
            for message in selected:
                _dict = {
                    'sender': str(message.sender),
                    'message': message.text,
                    'received_room_id': uuid,
                    'date_created': message.date_created.strftime("%d %b %Y %H:%M:%S %Z")
                }
                messages_array.append(_dict)
            return JsonResponse(messages_array, safe=False)

        else:
            return Http404(_("Sorry! We can't find what you're looking for."))
    else:
        return Http404(_("Sorry! We can't find what you're looking for."))
