from django.contrib.auth import get_user_model
from django.urls import reverse

User = get_user_model()


def test_staff_dashboard_sets_return_url(client, db):
    staff = User.objects.create_user(
        phone_number="06119999", is_staff=True, phone_verified=True
    )
    client.force_login(staff)
    dash = reverse("dashboard:listings")
    response = client.get(dash)
    assert response.status_code == 200
    assert client.session["staff_return_url"] == dash


def test_staff_listing_detail_returns_to_dashboard(client, listing):
    staff = User.objects.create_user(
        phone_number="06118888", is_staff=True, phone_verified=True
    )
    client.force_login(staff)
    dash = reverse("dashboard:listings")
    client.get(dash)
    response = client.get(listing.get_absolute_url())
    assert response.status_code == 200
    html = response.content.decode()
    assert f'href="{dash}"' in html
    assert "Retour au tableau de bord" in html


def test_member_listing_detail_back_is_search(client, listing, user):
    client.force_login(user)
    response = client.get(listing.get_absolute_url())
    assert response.status_code == 200
    html = response.content.decode()
    assert reverse("listings:search") in html
    assert "Retour au tableau de bord" not in html
