import pytest
from django.contrib.auth import get_user_model
from django.core.cache import cache

from apps.listings.models import Listing
from apps.locations.models import City, District, Province
from apps.taxonomy.models import Category, Profession, ProfessionAlias

User = get_user_model()


@pytest.fixture(autouse=True)
def _cache_isole():
    """Les compteurs de limitation de débit vivent dans le cache du processus :
    sans purge, un test épuise le quota des suivants."""
    cache.clear()
    yield
    cache.clear()


@pytest.fixture
def user(db):
    return User.objects.create_user(phone_number="06200010", phone_verified=True)


@pytest.fixture
def other(db):
    return User.objects.create_user(phone_number="06200011", phone_verified=True)


@pytest.fixture
def profession(db):
    category = Category.objects.create(name="Maison & Famille", slug="maison-famille")
    job = Profession.objects.create(category=category, name="Femme de ménage")
    ProfessionAlias.objects.create(profession=job, name="ménagère")
    ProfessionAlias.objects.create(profession=job, name="employée de maison")
    return job


@pytest.fixture
def city(db):
    province = Province.objects.create(name="Estuaire")
    libreville = City.objects.create(province=province, name="Libreville", is_popular=True)
    District.objects.create(city=libreville, name="Angondjé")
    return libreville


@pytest.fixture
def listing(user, profession, city):
    item = Listing.objects.create(
        author=user,
        listing_type=Listing.Type.EMPLOYMENT,
        profession=profession,
        description="Je recherche une nounou sérieuse pour deux enfants à Libreville.",
        province=city.province,
        city=city,
        salary_type=Listing.SalaryType.MONTH,
        salary_amount=200000,
        duration=Listing.Duration.PERMANENT,
        availability=Listing.Availability.IMMEDIATE,
    )
    item.publish()
    return item
