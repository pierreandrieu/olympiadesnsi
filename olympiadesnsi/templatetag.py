from django import template

register = template.Library()


@register.filter(name='is_organisateur')
def is_organisateur(user):
    return user.groups.filter(name='Organisateur').exists()


@register.filter(name='is_participant')
def is_organisateur(user):
    return user.groups.filter(name='Participant').exists()
