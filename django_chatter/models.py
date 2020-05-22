# coding: utf-8
import uuid

from django.conf import settings
from django.db import models
from django.utils.module_loading import import_string
from django.utils.translation import gettext as _
from django.contrib.auth.models import Group


def get_text_field(**kwargs):
    """It allows to customize the field in order to make it html for example"""
    config = getattr(settings, "CHATTER_TEXTFIELD_CONFIG", {})
    config.setdefault('field', "django.db.models.TextField")
    config.setdefault('attributes', {})
    text_field = import_string(config['field'])
    attributes = config['attributes']
    for key in kwargs:
        attributes.setdefault(key, kwargs[key])
    return text_field(**attributes)


class UserProfile(models.Model):
    user = models.OneToOneField(settings.AUTH_USER_MODEL,
                                on_delete=models.CASCADE,
                                related_name='profile')
    last_visit = models.DateTimeField()


# This model is used to give date and time when a message was created/modified.
class DateTimeModel(models.Model):
    date_created = models.DateTimeField(verbose_name=_("date created"),
                                        auto_now_add=True)
    date_modified = models.DateTimeField(verbose_name=_("date modified"),
                                         auto_now=True)

    class Meta:
        abstract = True


class Room(DateTimeModel):
    id = models.UUIDField(primary_key=True,
                          default=uuid.uuid4,
                          editable=False)
    name = models.CharField(verbose_name=_("name"),
                            max_length=350,
                            null=True, blank=True)
    members = models.ManyToManyField(settings.AUTH_USER_MODEL,
                                     verbose_name=_("members"),
                                     related_name='members',
                                     blank=True)

    members_groups = models.ManyToManyField(Group,
                                            verbose_name=_("members groups"),
                                            related_name='members_groups',
                                            blank=True)

    def __str__(self):
        if self.name:
            return self.name
        members_limit = 20
        members_qs = self.get_members_all()
        members_total = members_qs.count()
        members_list = []
        for member in members_qs[:members_limit]:
            members_list.append(str(member))
        s = ", ".join(members_list)
        if members_total > members_limit:
            s += "..."
        return s

    def is_member(self, user):
        """Checks whether the user is a member of the room
        :rtype bool
        """
        return self.members.filter(pk=user.pk).exists() or \
               self.members_groups.filter(user__pk=user.pk).exists()

    def get_members_all(self, excluding=None, pks=False):
        """Returns all members of the room following the configuration criteria"""
        members = self.members.union(
            self.members.model.objects.filter(
                groups__in=self.members_groups.all()))
        if excluding is not None:
            members = members.exclude(**excluding)
        if pks:
            members = members.values_list('pk', flat=pks)
        return members

    class Meta:
        verbose_name = _("Room")
        verbose_name_plural = _("Rooms")


class Message(DateTimeModel):
    sender = models.ForeignKey(settings.AUTH_USER_MODEL,
                               verbose_name=_("sender"),
                               on_delete=models.CASCADE,
                               related_name='sender')
    room = models.ForeignKey(Room,
                             verbose_name=_("room"),
                             on_delete=models.CASCADE)
    text = get_text_field(verbose_name=_("text"))
    recipients = models.ManyToManyField(settings.AUTH_USER_MODEL,
                                        verbose_name=_("recipients"),
                                        related_name='recipients')

    def __str__(self):
        return _(f'sent by "{self.sender}" in room "{self.room}"')

    class Meta:
        ordering = ['-date_created']
        verbose_name = _("Message")
        verbose_name_plural = _("Messages")
