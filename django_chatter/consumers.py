import bleach
from channels.db import database_sync_to_async
from channels.generic.websocket import AsyncJsonWebsocketConsumer
from uuid import UUID

from django_chatter.models import Room, Message


@database_sync_to_async
def get_room(room_id, multitenant=False, schema_name=None):
    if multitenant:
        if not schema_name:
            raise AttributeError("Multitenancy support error: \
                scope does not have multitenancy details added. \
                did you forget to add ChatterMTMiddlewareStack to your routing?")
        else:
            from django_tenants.utils import schema_context
            with schema_context(schema_name):
                return Room.objects.get(id=room_id)
    else:
        return Room.objects.get(id=room_id)


@database_sync_to_async
def save_message(room, sender, text, multitenant=False, schema_name=None):
    if multitenant:
        if not schema_name:
            raise AttributeError("Multitenancy support error: \
                scope does not have multitenancy details added. \
                did you forget to add ChatterMTMiddlewareStack to your routing?")
        else:
            from django_tenants.utils import schema_context
            with schema_context(schema_name):
                new_message = Message(room=room, sender=sender, text=text)
                new_message.save()
                new_message.recipients.add(sender)
                new_message.save()
                room.date_modified = new_message.date_modified
                room.save()
                return new_message.date_created
    else:
        new_message = Message(room=room, sender=sender, text=text)
        new_message.save()
        new_message.recipients.add(sender)
        new_message.save()
        room.date_modified = new_message.date_modified
        room.save()
        return new_message.date_created


class ChatConsumer(AsyncJsonWebsocketConsumer):
    """
        WebSocket methods below
    """

    async def connect(self):
        self.user = self.scope['user']
        self.room_users = []  # Cache room usernames to send alerts
        self.schema_name = self.scope.get('schema_name', None)
        self.multitenant = self.scope.get('multitenant', False)

        for param in self.scope['path'].split('/'):
            try:
                room_id = UUID(param, version=4)
                break
            except ValueError:
                continue
        else:
            raise Exception("missing 'uuid'")

        # Check if the user connecting to the room's websocket belongs in the room
        try:
            self.room = await get_room(room_id, self.multitenant, self.schema_name)
            if self.multitenant:
                from django_tenants.utils import schema_context
                with schema_context(self.schema_name):
                    if self.room.members.filter(pk=self.user.pk).exists():
                        self.room_group_name = f'chat_{self.room.pk}'
                        await self.channel_layer.group_add(
                            self.room_group_name,
                            self.channel_name
                        )
                        await self.accept()

                        for user in self.room.members.all():
                            self.room_users.append(user.pk)
                    else:
                        await self.disconnect(403)
            else:
                if self.room.members.filter(pk=self.user.pk).exists():
                    self.room_group_name = f'chat_{self.room.pk}'
                    await self.channel_layer.group_add(
                        self.room_group_name,
                        self.channel_name
                    )
                    await self.accept()

                    for user in self.room.members.all():
                        self.room_users.append(user.pk)
                else:
                    await self.disconnect(403)
        except Exception as ex:
            raise ex

    async def disconnect(self, close_code):
        await self.channel_layer.group_discard(
            self.room_group_name,
            self.channel_name
        )

    def validate_session(self, data):
        return data['sender']['id'] == self.user.pk or \
               data['room_id'] == str(self.room.pk)

    async def receive_json(self, data, **kwargs):
        if not self.validate_session(data):
            await self.disconnect(403)

        message_type = data['message_type']
        if message_type == "text":
            message = data['message']
            room_id = data['room_id']

            # Clean code off message if message contains code
            self.message_safe = bleach.clean(message)

            time = await save_message(self.room,
                                      self.user,
                                      self.message_safe,
                                      self.multitenant,
                                      self.schema_name)
            time = time.strftime("%d %b %Y %H:%M:%S %Z")
            await self.channel_layer.group_send(
                self.room_group_name,
                {
                    'type': 'send_to_websocket',
                    'message_type': 'text',
                    'message': self.message_safe,
                    'date_created': time,
                    'sender': {
                        'id': self.user.pk,
                        '__str__': str(self.user)
                    },
                    'room_id': room_id,
                }
            )

            for user_pk in self.room_users:
                if user_pk != self.user.pk:
                    await self.channel_layer.group_send(
                        f'user_{user_pk}',
                        {
                            'type': 'receive_json',
                            'message_type': 'text',
                            'message': self.message_safe,
                            'date_created': time,
                            'sender': {
                                'id': self.user.pk,
                                '__str__': str(self.user)
                            },
                            'room_id': room_id,
                        }
                    )

    async def send_to_websocket(self, event):
        await self.send_json(event)


class AlertConsumer(AsyncJsonWebsocketConsumer):
    """
        WebSocket methods below
    """

    async def connect(self):
        self.user = self.scope['user']
        self.user_group_name = f'user_{self.user.pk}'
        await self.channel_layer.group_add(
            self.user_group_name,
            self.channel_name
        )
        await self.accept()

    async def disconnect(self, close_code):
        await self.channel_layer.group_discard(
            self.user_group_name,
            self.channel_name
        )

    async def receive_json(self, data, **kwargs):
        # Check if the data has been sent to this consumer by the currently
        # logged in user

        data['type'] = 'send_to_websocket'
        await self.channel_layer.group_send(self.user_group_name, data)

    async def send_to_websocket(self, event):
        await self.send_json(event)
