# import the logging library
import logging
from django.conf import settings
from django.contrib.auth import get_user_model
from django.contrib.auth.decorators import login_required
from django.contrib.auth.mixins import LoginRequiredMixin
from django.core.paginator import Paginator, EmptyPage, PageNotAnInteger
from django.http import HttpResponseRedirect, JsonResponse, Http404
from django.urls import reverse
from django.utils.decorators import method_decorator
from django.utils.translation import gettext as _
from django.views import View
from django.views.generic.base import TemplateView

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

    def get_websocket_url(self):
        ws_url = getattr(settings, "CHATTER_WEBSOCKET_URL", None)
        if ws_url is None:
            protocol = "wss://" if self.request.is_secure() else "ws://"
            ws_url = protocol + self.request.get_host()
        return ws_url

    # This gets executed whenever a room exists
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['websocket_base_url'] = self.get_websocket_url()
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
                room_name = str(room)
            context['room_uuid_json'] = kwargs.get('uuid')
            context['latest_messages_curr_room'] = latest_messages_curr_room
            context['room_name'] = room_name
            context['base_template'] = import_base_template()

            # Add rooms with unread messages
            rooms_list = Room.objects.filter(members__in=[user]) \
                             .order_by('-date_modified')[:10]
            rooms_with_unread = []
            # Go through each list of rooms and check if the last message was unread
            # and add each last message to the context
            for room in rooms_list:
                try:
                    message = room.message_set.all().order_by('-id')[0]
                except IndexError as e:
                    continue
                if not message.recipients.filter(pk=user.pk).exists():
                    rooms_with_unread.append(room.pk)
            context['rooms_list'] = rooms_list
            context['rooms_with_unread'] = rooms_with_unread

            return context
        else:
            raise Http404(_("Sorry! What you're looking for isn't here."))


@login_required
def users_list(request):
    """The following functions deal with AJAX requests"""
    if request.is_ajax():
        data_array = []
        for user in User.objects.all():
            data = {
                'id': user.pk,
                'text': str(user)
            }
            data_array.append(data)
        return JsonResponse(data_array, safe=False)


class ChatUrlView(View):
    http_method_names = ['post']

    @method_decorator(login_required)
    def post(self, request):
        url = self.get_url(request)
        if request.is_ajax():
            response = JsonResponse({'url': url})
        else:
            response = HttpResponseRedirect(url)
        return response

    def get_room(self, request):
        """
        Use the util room creation function to create room for one/two
        user(s). This can be extended in the future to add multiple users
        in a group chat.
        """
        user = request.user
        target_user = User.objects.get(pk=request.POST.get('target_user'))

        if user == target_user:
            room = create_room([user])
        else:
            room = create_room([user, target_user])
        return room

    def get_url(self, request):
        room = self.get_room(request)
        return reverse('django_chatter:chatroom', args=[room.pk])


@login_required
def get_messages(request, uuid):
    """Ajax request to fetch earlier messages"""
    if request.is_ajax():
        user = request.user
        room = Room.objects.get(pk=uuid)
        if room.members.filter(pk=user.pk).exists():
            messages_qs = room.message_set.all()
            page = request.GET.get('page')
            paginator = Paginator(messages_qs, 20)
            try:
                selected = paginator.page(page)
            except PageNotAnInteger:
                selected = paginator.page(1)
            except EmptyPage:
                selected = []
            messages = []
            for message in selected:
                data = {
                    'sender': {
                        'name': str(message.sender),
                        'id': message.sender.pk
                    },
                    'message': message.text,
                    'received_room_id': uuid,
                    'date_created': message.date_created.strftime("%d %b %Y %H:%M:%S %Z")
                }
                messages.append(data)
            return JsonResponse(messages, safe=False)

        else:
            return Http404(_("Sorry! We can't find what you're looking for."))
    else:
        return Http404(_("Sorry! We can't find what you're looking for."))
