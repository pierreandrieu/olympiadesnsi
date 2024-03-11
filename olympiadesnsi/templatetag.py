from django import template
from django.contrib.auth.models import Group

register = template.Library()


@register.filter(name='is_organisateur')
def is_organisateur(user):
    return user.groups.filter(name='Organisateur').exists()


@register.filter(name='is_participant')
def is_organisateur(user):
    return user.groups.filter(name='Participant').exists()
