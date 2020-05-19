# coding: utf-8
import uuid

from django.conf import settings
from django.db import models
from django.utils.functional import cached_property
from django.utils.translation import gettext as _


class UserProfile(models.Model):
    user = models.OneToOneField(settings.AUTH_USER_MODEL,
                                on_delete=models.CASCADE,
                                related_name='profile')
    last_visit = models.DateTimeField()


# This model is used to give date and time when a message was created/modified.
class DateTimeModel(models.Model):
    date_created = models.DateTimeField(auto_now_add=True)
    date_modified = models.DateTimeField(auto_now=True)

    class Meta:
        abstract = True


class Room(DateTimeModel):
    id = models.UUIDField(primary_key=True,
                          default=uuid.uuid4,
                          editable=False)
    name = models.CharField("Name", max_length=350,
                            null=True, blank=True)
    members = models.ManyToManyField(settings.AUTH_USER_MODEL,
                                     related_name='members')

    def __str__(self):
        if self.name:
            return self.name

        memberset = self.members.all()
        members_list = []
        for member in memberset:
            members_list.append(str(member))
        return ", ".join(members_list)

    def is_member(self, user):
        """Checks whether the user is a member of the room
        :rtype bool
        """
        return self.members.filter(pk=user.pk).exists()

    @cached_property
    def members_pks_cache(self):
        return list(self.members.values_list('pk', flat=True))

    class Meta:
        verbose_name = _("Room")
        verbose_name_plural = _("Rooms")


class Message(DateTimeModel):
    sender = models.ForeignKey(settings.AUTH_USER_MODEL,
                               on_delete=models.CASCADE,
                               related_name='sender')
    room = models.ForeignKey(Room, on_delete=models.CASCADE)
    text = models.TextField()
    recipients = models.ManyToManyField(settings.AUTH_USER_MODEL,
                                        related_name='recipients')

    def __str__(self):
        return f'{self.text} sent by "{self.sender}" in Room "{self.room}"'

    class Meta:
        ordering = ['-id']
        verbose_name = _("Message")
        verbose_name_plural = _("Messages")
