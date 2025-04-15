import pytest
from django.urls import reverse
from django.test import Client
from epreuve.models import Epreuve
from django.contrib.auth.models import User


@pytest.mark.django_db
def test_homepage_affiche_epreuve_publique():
    client = Client()

    user = User.objects.create(username="referent")
    epreuve = Epreuve.objects.create(
        nom="Épreuve publique 2025",
        code="PUB25",
        date_debut="2025-01-01T10:00:00Z",
        date_fin="2025-01-02T10:00:00Z",
        referent=user,
        inscription_externe=True
    )

    response = client.get(reverse("home"))
    assert response.status_code == 200
    content = response.content.decode()
    assert "Épreuve publique 2025" in content
    assert "Nombre d'équipes inscrites" in content
