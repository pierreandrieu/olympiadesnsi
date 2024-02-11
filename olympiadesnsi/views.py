from django.shortcuts import render


def ratelimited_error(request, exception):
    return render(request, 'olympiadesnsi/ratelimited.html', status=429)