"""Filtres de la page de recherche : effet réel et conservation de l'état."""

import pytest
from django.urls import reverse

from apps.listings.models import Listing
from apps.locations.models import City, Province


@pytest.fixture
def catalogue(db, user, profession):
    """Un jeu d'annonces couvrant chaque axe de filtrage."""
    estuaire = Province.objects.create(name="Estuaire")
    ogooue = Province.objects.create(name="Ogooué-Maritime")
    libreville = City.objects.create(province=estuaire, name="Libreville")
    port_gentil = City.objects.create(province=ogooue, name="Port-Gentil")

    def creer(**kwargs):
        defaults = dict(
            author=user,
            profession=profession,
            description="Description suffisamment longue pour l'annonce.",
            salary_type=Listing.SalaryType.MONTH,
            availability=Listing.Availability.IMMEDIATE,
        )
        listing = Listing.objects.create(**{**defaults, **kwargs})
        listing.publish()
        return listing

    return {
        "emploi_lbv": creer(
            title="Nounou Libreville",
            listing_type=Listing.Type.EMPLOYMENT,
            province=estuaire,
            city=libreville,
            duration=Listing.Duration.PERMANENT,
            salary_amount=250000,
        ),
        "emploi_pog": creer(
            title="Gardien Port-Gentil",
            listing_type=Listing.Type.EMPLOYMENT,
            province=ogooue,
            city=port_gentil,
            duration=Listing.Duration.PERMANENT,
            salary_amount=120000,
        ),
        "mission_lbv": creer(
            title="Déménagement urgent",
            listing_type=Listing.Type.MISSION,
            province=estuaire,
            city=libreville,
            duration=Listing.Duration.FEW_DAYS,
            salary_amount=40000,
        ),
    }


def resultats(client, **params):
    """Titres des annonces rendues pour ces paramètres."""
    response = client.get(reverse("listings:search"), params)
    assert response.status_code == 200
    return {listing.title for listing in response.context["listings"]}


# ── Chaque filtre isolément ─────────────────────────────────────────────


@pytest.mark.django_db
def test_sans_filtre_tout_est_visible(client, catalogue):
    assert len(resultats(client)) == 3


@pytest.mark.django_db
def test_filtre_type(client, catalogue):
    assert resultats(client, type="mission") == {"Déménagement urgent"}
    assert len(resultats(client, type="employment")) == 2


@pytest.mark.django_db
def test_filtre_ville(client, catalogue):
    assert resultats(client, city_name="Port-Gentil") == {"Gardien Port-Gentil"}


@pytest.mark.django_db
def test_filtre_province(client, catalogue):
    province = Province.objects.get(name="Ogooué-Maritime")
    assert resultats(client, province=province.pk) == {"Gardien Port-Gentil"}


@pytest.mark.django_db
def test_filtre_duree(client, catalogue):
    assert resultats(client, duration=Listing.Duration.FEW_DAYS) == {"Déménagement urgent"}


@pytest.mark.django_db
def test_filtre_salaire_minimum(client, catalogue):
    assert resultats(client, salary_min="200000") == {"Nounou Libreville"}


@pytest.mark.django_db
def test_filtre_salaire_non_numerique_est_ignore(client, catalogue):
    """Une valeur aberrante ne doit pas provoquer d'erreur 500."""
    assert len(resultats(client, salary_min="beaucoup")) == 3


# ── Combinaisons ────────────────────────────────────────────────────────


@pytest.mark.django_db
def test_filtres_se_combinent(client, catalogue):
    assert resultats(client, type="employment", city_name="Libreville") == {
        "Nounou Libreville"
    }


@pytest.mark.django_db
def test_recherche_texte_et_filtre_se_combinent(client, catalogue):
    assert resultats(client, q="gardien", type="employment") == {"Gardien Port-Gentil"}
    assert resultats(client, q="gardien", type="mission") == set()


# ── Conservation de l'état entre formulaires ────────────────────────────


@pytest.mark.django_db
def test_les_formulaires_reconduisent_les_filtres_actifs(client, catalogue):
    """Chaque formulaire doit rejouer les filtres qu'il n'affiche pas."""
    response = client.get(
        reverse("listings:search"),
        {"q": "nounou", "type": "employment", "city_name": "Libreville", "sort": "salary"},
    )
    html = response.content.decode()
    for attendu in (
        '<input type="hidden" name="type" value="employment">',
        '<input type="hidden" name="city_name" value="Libreville">',
        '<input type="hidden" name="sort" value="salary">',
        '<input type="hidden" name="q" value="nounou">',
    ):
        assert attendu in html, attendu


@pytest.mark.django_db
def test_le_panneau_restitue_les_valeurs_choisies(client, catalogue):
    response = client.get(
        reverse("listings:search"),
        {"type": "mission", "duration": Listing.Duration.FEW_DAYS, "salary_min": "30000"},
    )
    html = response.content.decode()
    assert 'value="mission" checked' in html
    assert f'<option value="{Listing.Duration.FEW_DAYS}" selected>' in html
    assert 'name="salary_min" min="0" step="5000" value="30000"' in html


@pytest.mark.django_db
def test_compteur_de_filtres_actifs(client, catalogue):
    """Ni la recherche texte ni le tri ne comptent comme des filtres."""
    html = client.get(
        reverse("listings:search"), {"q": "nounou", "sort": "salary"}
    ).content.decode()
    assert "filter-count" not in html

    html = client.get(
        reverse("listings:search"), {"type": "mission", "city_name": "Libreville"}
    ).content.decode()
    assert '<span class="filter-count">2</span>' in html


@pytest.mark.django_db
def test_pagination_conserve_les_filtres(client, user, profession):
    """« ?q=…&page=N » perdait type, ville, durée et tri à chaque page."""
    province = Province.objects.create(name="Estuaire")
    city = City.objects.create(province=province, name="Libreville")
    for index in range(15):
        listing = Listing.objects.create(
            author=user,
            title=f"Mission {index}",
            listing_type=Listing.Type.MISSION,
            profession=profession,
            description="Description suffisamment longue pour l'annonce.",
            province=province,
            city=city,
            duration=Listing.Duration.FEW_DAYS,
            salary_type=Listing.SalaryType.DAY,
            salary_amount=10000,
            availability=Listing.Availability.IMMEDIATE,
        )
        listing.publish()

    response = client.get(
        reverse("listings:search"), {"type": "mission", "city_name": "Libreville"}
    )
    html = response.content.decode()
    assert response.context["page_obj"].has_next()
    assert "type=mission" in html
    assert "city_name=Libreville" in html
    assert "page=2" in html

    # La page 2 filtre toujours.
    page2 = client.get(
        reverse("listings:search"),
        {"type": "mission", "city_name": "Libreville", "page": "2"},
    )
    assert page2.context["page_obj"].number == 2
    assert all(listing.listing_type == "mission" for listing in page2.context["listings"])
