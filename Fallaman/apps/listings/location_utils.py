from apps.locations.models import City, District, Province
from apps.taxonomy.models import Profession


def resolve_profession(job_name: str):
    name = (job_name or "").strip()
    if not name:
        return None, ""
    profession = Profession.objects.filter(name__iexact=name).first()
    if profession:
        return profession, ""
    return None, name


def resolve_location(province_name: str, city_name: str, district_name: str = ""):
    province_name = (province_name or "").strip()
    city_name = (city_name or "").strip()
    district_name = (district_name or "").strip()

    if not province_name or not city_name:
        raise ValueError("Province et ville sont obligatoires.")

    province = Province.objects.filter(name__iexact=province_name).first()
    if not province:
        province = Province.objects.create(
            name=province_name,
            sort_order=Province.objects.count() + 1,
        )

    city = City.objects.filter(province=province, name__iexact=city_name).first()
    if not city:
        city = City.objects.create(province=province, name=city_name)

    district = None
    if district_name:
        district = District.objects.filter(city=city, name__iexact=district_name).first()
        if not district:
            district = District.objects.create(city=city, name=district_name)

    return province, city, district
