from apps.listings.models import Listing
from apps.listings.services import search_listings


def test_search_understands_alias(listing):
    qs = search_listings(Listing.objects.published(), "ménagère")
    assert listing in list(qs)


def test_search_page_without_account(client, listing):
    response = client.get("/rechercher/", {"q": "ménagère"})
    assert response.status_code == 200
    assert "ménage" in response.content.decode().lower() or listing.title in response.content.decode()


def test_detail_is_public(client, listing):
    response = client.get(listing.get_absolute_url())
    assert response.status_code == 200
    assert "Je suis intéressé" in response.content.decode()


def test_publish_requires_login(client):
    response = client.get("/publier/")
    assert response.status_code == 302


def test_author_cannot_be_edited_by_other(client, listing, other):
    client.force_login(other)
    response = client.post(f"/annonces/{listing.pk}/pourvu/")
    listing.refresh_from_db()
    assert listing.status != Listing.Status.FILLED
    assert response.status_code in {302, 404}
