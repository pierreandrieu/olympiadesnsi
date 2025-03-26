from django.contrib import admin
from django.urls import include, path
from login.views import custom_logout

handler429 = 'olympiadesnsi.views.ratelimited_error'
urlpatterns = [
    # Django admin
    path("admin/", admin.site.urls),

    # CAPTCHA en cas d'erreur répétée de mot de passe
    path("captcha/", include("captcha.urls")),

    # Applications internes
    path("", include("accueil.urls"), name="accueil"),
    path("login/", include("login.urls")),
    path("logout/", custom_logout, name="logout"),
    path("intranet/", include("intranet.urls")),
    path("epreuve/", include("epreuve.urls")),
    path("inscription/", include("inscription.urls")),
]
