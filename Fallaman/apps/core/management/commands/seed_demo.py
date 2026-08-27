from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError
from django.utils.text import slugify

from apps.listings.models import Listing
from apps.locations.models import City, District, Province
from apps.taxonomy.models import Category, Profession, ProfessionAlias

CATEGORIES = [
    (
        "Maison & Famille",
        "home",
        [
            ("Nounou", ["nounou", "baby sitter", "garde d'enfants", "nounou à domicile"], True),
            ("Femme de ménage", ["ménagère", "employée de maison", "agent d'entretien", "femme de ménage"], True),
            ("Homme de ménage", ["ménager", "homme de ménage", "agent d'entretien"], False),
            ("Gardien", ["gardien", "veilleur", "gardien de maison"], True),
            ("Jardinier", ["jardinier", "entretien jardin"], False),
            ("Aide à domicile", ["aide a domicile", "auxiliaire de vie"], False),
            ("Cuisinier / Cuisinière", ["cuisinier", "cuisinière", "cuistot"], False),
            ("Blanchisseur / Blanchisseuse", ["blanchisseur", "lavandière"], False),
            ("Repassage", ["repassage", "repasser"], False),
            ("Baby-sitter", ["baby-sitter", "babysitter", "garde d'enfant"], False),
            ("Assistant(e) familial(e)", ["assistante familiale", "assistant familial"], False),
        ],
    ),
    (
        "Transport & Livraison",
        "truck",
        [
            ("Chauffeur particulier", ["chauffeur", "chauffeur privé", "driver"], True),
            ("Chauffeur taxi", ["taxi", "chauffeur taxi"], False),
            ("Chauffeur poids lourd", ["poids lourd", "camion"], False),
            ("Chauffeur de camion", ["chauffeur camion"], False),
            ("Conducteur", ["conducteur"], False),
            ("Livreur", ["livreur", "livraison"], False),
            ("Coursier", ["coursier", "moto"], False),
            ("Manœuvre / aide-chauffeur", ["aide chauffeur", "manoeuvre chauffeur"], False),
            ("Mécanicien", ["mécanicien", "garage"], False),
        ],
    ),
    (
        "BTP & Construction",
        "bricks",
        [
            ("Maçon", ["maçon", "macon", "maçonnerie"], True),
            ("Aide-maçon", ["aide macon", "manoeuvre macon"], False),
            ("Électricien", ["electricien", "électricité"], False),
            ("Plombier", ["plombier", "plomberie"], False),
            ("Carreleur", ["carreleur", "carrelage"], False),
            ("Peintre", ["peintre", "peinture"], False),
            ("Soudeur", ["soudeur", "soudure"], False),
            ("Menuisier", ["menuisier", "bois"], False),
            ("Charpentier", ["charpentier"], False),
            ("Ferrailleur", ["ferrailleur"], False),
            ("Coffreur", ["coffreur"], False),
            ("Manœuvre", ["manoeuvre", "manœuvre", "aide chantier"], False),
            ("Chef de chantier", ["chef de chantier", "conducteur de travaux"], False),
        ],
    ),
    (
        "Agriculture & Entretien extérieur",
        "leaf",
        [
            ("Débroussailleur", ["débroussailleur", "debroussailleur", "débroussage", "debroussage", "entretien terrain"], True),
            ("Jardinier", ["jardinier"], False),
            ("Agriculteur", ["agriculteur"], False),
            ("Ouvrier agricole", ["ouvrier agricole"], False),
            ("Élagueur", ["elagueur", "élagage"], False),
            ("Paysagiste", ["paysagiste"], False),
            ("Gardien de plantation", ["gardien plantation"], False),
            ("Manœuvre agricole", ["manoeuvre agricole"], False),
        ],
    ),
    (
        "Restauration & Hôtellerie",
        "utensils",
        [
            ("Serveur / Serveuse", ["serveur", "serveuse", "service"], True),
            ("Cuisinier / Cuisinière", ["cuisinier", "cuisiniere"], False),
            ("Aide-cuisinier", ["aide cuisinier", "commis"], False),
            ("Plongeur", ["plongeur", "plonge"], False),
            ("Barman / Barmaid", ["barman", "barmaid", "bar"], False),
            ("Gérant(e) de bar", ["gerant de bar"], False),
            ("Réceptionniste", ["receptionniste"], False),
            ("Femme / Homme de chambre", ["femme de chambre", "homme de chambre"], False),
            ("Agent d'entretien", ["agent d'entretien", "entretien"], False),
            ("Commis de cuisine", ["commis de cuisine"], False),
        ],
    ),
    (
        "Commerce & Vente",
        "shop",
        [
            ("Vendeur / Vendeuse", ["vendeur", "vendeuse"], False),
            ("Caissier / Caissière", ["caissier", "caissiere"], False),
            ("Commercial", ["commercial"], False),
            ("Agent commercial", ["agent commercial"], False),
            ("Gérant de boutique", ["gerant boutique"], False),
            ("Responsable magasin", ["responsable magasin"], False),
            ("Magasinier", ["magasinier"], False),
            ("Rayonniste", ["rayonniste"], False),
            ("Gestionnaire de stock", ["stock", "gestionnaire de stock"], False),
        ],
    ),
    (
        "Beauté & Bien-être",
        "sparkle",
        [
            ("Coiffeur / Coiffeuse", ["coiffeur", "coiffeuse", "salon"], False),
            ("Barbier", ["barbier"], False),
            ("Esthéticienne", ["estheticienne"], False),
            ("Maquilleur / Maquilleuse", ["maquilleur", "maquilleuse"], False),
            ("Manucure / pédicure", ["manucure", "pedicure"], False),
            ("Masseuse / masseur", ["masseur", "masseuse"], False),
            ("Prothésiste ongulaire", ["prothesiste ongulaire", "ongles"], False),
        ],
    ),
    (
        "Artisanat & Réparation",
        "wrench",
        [
            ("Mécanicien", ["mecanicien"], False),
            ("Électricien", ["electricien"], False),
            ("Électronicien", ["electronicien"], False),
            ("Réparateur téléphone", ["reparateur telephone", "telephone"], False),
            ("Informaticien", ["informaticien"], False),
            ("Frigoriste", ["frigoriste"], False),
            ("Climaticien", ["climaticien", "climatisation", "clim"], False),
            ("Couturier / Couturière", ["couturier", "couturiere", "couture"], False),
            ("Cordonnier", ["cordonnier"], False),
            ("Tapissier", ["tapissier"], False),
            ("Vitrier", ["vitrier"], False),
        ],
    ),
    (
        "Informatique & Services",
        "laptop",
        [
            ("Informaticien", ["informaticien"], False),
            ("Développeur", ["developpeur", "programmeur"], False),
            ("Graphiste", ["graphiste"], False),
            ("Community manager", ["community manager"], False),
            ("Photographe", ["photographe"], False),
            ("Vidéaste", ["videaste"], False),
            ("Webmaster", ["webmaster"], False),
            ("Assistant administratif", ["assistant administratif"], False),
            ("Secrétaire", ["secretaire"], False),
            ("Comptable", ["comptable"], False),
        ],
    ),
    (
        "Administration & Entreprise",
        "building",
        [
            ("Secrétaire", ["secretaire"], False),
            ("Assistant administratif", ["assistant administratif"], False),
            ("Comptable", ["comptable"], False),
            ("Responsable commercial", ["responsable commercial"], False),
            ("Ressources humaines", ["rh", "ressources humaines"], False),
            ("Agent d'accueil", ["accueil"], False),
            ("Agent de sécurité", ["agent de securite"], False),
            ("Téléconseiller", ["teleconseiller"], False),
            ("Assistant(e) de direction", ["assistant de direction"], False),
        ],
    ),
    (
        "Logistique & Manutention",
        "box",
        [
            ("Manutentionnaire", ["manutentionnaire"], False),
            ("Magasinier", ["magasinier"], False),
            ("Préparateur de commandes", ["preparateur de commandes"], False),
            ("Cariste", ["cariste"], False),
            ("Agent de livraison", ["agent de livraison"], False),
            ("Agent logistique", ["logistique"], False),
            ("Déménageur", ["demenageur", "déménagement"], False),
            ("Aide-déménageur", ["aide demenageur"], False),
        ],
    ),
    (
        "Sécurité",
        "shield",
        [
            ("Gardien", ["gardien"], False),
            ("Agent de sécurité", ["agent de securite", "securite"], False),
            ("Vigile", ["vigile"], False),
            ("Maître-chien", ["maitre chien"], False),
            ("Surveillant", ["surveillant"], False),
        ],
    ),
    (
        "Éducation & Aide scolaire",
        "book",
        [
            ("Enseignant", ["enseignant", "professeur"], False),
            ("Professeur particulier", ["prof particulier", "cours particuliers"], False),
            ("Répétiteur", ["repetiteur", "répétiteur"], False),
            ("Éducateur", ["educateur"], False),
            ("Formateur", ["formateur"], False),
            ("Assistant scolaire", ["assistant scolaire"], False),
            ("Baby-sitter", ["baby-sitter"], False),
        ],
    ),
]

LOCATIONS = {
    "Estuaire": {
        "Libreville": [
            "Angondjé",
            "Nzeng-Ayong",
            "Akébé",
            "Batterie IV",
            "Glass",
            "Louis",
            "Nombakélé",
            "Mindoubé",
            "Lalala",
            "Sablière",
            "Gué-Gué",
            "Charbonnages",
            "Cité Damas",
            "PK8",
            "PK12",
        ],
        "Akanda": ["Okala", "Angondjé", "Cap Estérias"],
        "Owendo": ["Owendo centre", "Alenakiri"],
        "Ntoum": ["Ntoum centre"],
    },
    "Ogooué-Maritime": {"Port-Gentil": ["Centre-ville", "Grand Village", "Château"]},
    "Haut-Ogooué": {"Franceville": ["Potos", "Ongali"], "Moanda": ["Moanda centre"]},
    "Woleu-Ntem": {"Oyem": ["Oyem centre"]},
    "Moyen-Ogooué": {"Lambaréné": ["Lambaréné centre"]},
}

DEMO_LISTINGS = [
    {
        "job": "Nounou",
        "type": Listing.Type.EMPLOYMENT,
        "city": "Libreville",
        "district": "Angondjé",
        "salary": 200000,
        "salary_type": Listing.SalaryType.MONTH,
        "duration": Listing.Duration.PERMANENT,
        "description": "Je recherche une nounou sérieuse pour garder deux enfants du lundi au vendredi. Expérience souhaitée.",
        "author_name": "Amina",
        "phone": "+24106200001",
    },
    {
        "job": "Chauffeur particulier",
        "type": Listing.Type.EMPLOYMENT,
        "city": "Libreville",
        "district": "Nzeng-Ayong",
        "salary": 250000,
        "salary_type": Listing.SalaryType.MONTH,
        "duration": Listing.Duration.PERMANENT,
        "description": "Recherche chauffeur particulier disponible, permis B, bonne connaissance de Libreville.",
        "author_name": "Jean",
        "phone": "+24106200002",
    },
    {
        "job": "Maçon",
        "type": Listing.Type.MISSION,
        "city": "Owendo",
        "district": "Owendo centre",
        "salary": 15000,
        "salary_type": Listing.SalaryType.DAY,
        "duration": Listing.Duration.FEW_DAYS,
        "description": "Recherche maçon expérimenté pour travaux de rénovation pendant 5 jours.",
        "author_name": "Patrick",
        "phone": "+24106200003",
    },
    {
        "job": "Débroussailleur",
        "type": Listing.Type.MISSION,
        "city": "Ntoum",
        "district": "Ntoum centre",
        "salary": 50000,
        "salary_type": Listing.SalaryType.TOTAL,
        "duration": Listing.Duration.FEW_DAYS,
        "description": "Besoin d'un débroussailleur pour un terrain à Ntoum. Mission 2 jours.",
        "author_name": "Sylvie",
        "phone": "+24106200004",
    },
    {
        "job": "Serveur / Serveuse",
        "type": Listing.Type.EMPLOYMENT,
        "city": "Port-Gentil",
        "district": "Centre-ville",
        "salary": 180000,
        "salary_type": Listing.SalaryType.MONTH,
        "duration": Listing.Duration.FEW_MONTHS,
        "description": "Restaurant recherche serveuse dynamique pour le service du soir.",
        "author_name": "Michel",
        "phone": "+24106200005",
    },
    {
        "job": "Gardien",
        "type": Listing.Type.EMPLOYMENT,
        "city": "Franceville",
        "district": "Potos",
        "salary": 150000,
        "salary_type": Listing.SalaryType.MONTH,
        "duration": Listing.Duration.PERMANENT,
        "description": "Recherche gardien de maison, sérieux, pouvant aussi faire de petits entretiens.",
        "author_name": "Claire",
        "phone": "+24106200006",
    },
    {
        "job": "Femme de ménage",
        "type": Listing.Type.EMPLOYMENT,
        "city": "Libreville",
        "district": "Batterie IV",
        "salary": 120000,
        "salary_type": Listing.SalaryType.MONTH,
        "duration": Listing.Duration.PERMANENT,
        "description": "Recherche femme de ménage pour un appartement, 3 fois par semaine.",
        "author_name": "Nadia",
        "phone": "+24106200007",
    },
]


#: Mot de passe des comptes membres de démonstration (développement seulement).
DEMO_MEMBER_PASSWORD = "FallamanDemo2026"


class Command(BaseCommand):
    help = "Charge les catégories, localisations, annonces et comptes de test."

    def add_arguments(self, parser):
        parser.add_argument(
            "--with-accounts",
            action="store_true",
            help=(
                "Crée aussi les comptes de démonstration, dont un administrateur. "
                "Refusé hors développement."
            ),
        )
        parser.add_argument(
            "--reference-only",
            action="store_true",
            help="Ne charge que les métiers et localisations (sûr en production).",
        )

    def handle(self, *args, **options):
        self._seed_taxonomy()
        self._seed_locations()

        if options["reference_only"]:
            self.stdout.write(self.style.SUCCESS("Référentiel Fallaman chargé."))
            return

        self._seed_listings()

        if options["with_accounts"]:
            # Ces comptes ont des mots de passe connus et publiés dans le dépôt :
            # les créer sur un site en ligne revient à y poser une porte dérobée
            # administrateur.
            if not getattr(settings, "DEV_CONVENIENCES", False):
                raise CommandError(
                    "--with-accounts crée un administrateur au mot de passe connu. "
                    "Interdit hors développement (DEV_CONVENIENCES=False)."
                )
            self._seed_test_accounts()
        else:
            self.stdout.write(
                "Comptes de démonstration ignorés (utilisez --with-accounts en local)."
            )

        self.stdout.write(self.style.SUCCESS("Données Fallaman chargées."))

    def _seed_taxonomy(self):
        for order, (name, icon, professions) in enumerate(CATEGORIES, start=1):
            category, _ = Category.objects.update_or_create(
                slug=slugify(name)[:50],
                defaults={"name": name, "icon": icon, "sort_order": order, "is_active": True},
            )
            for p_order, (pname, aliases, popular) in enumerate(professions, start=1):
                profession, _ = Profession.objects.update_or_create(
                    category=category,
                    name=pname,
                    defaults={"is_popular": popular, "sort_order": p_order, "is_active": True},
                )
                for alias in aliases:
                    ProfessionAlias.objects.update_or_create(profession=profession, name=alias)

    def _seed_locations(self):
        for p_order, (province_name, cities) in enumerate(LOCATIONS.items(), start=1):
            province, _ = Province.objects.update_or_create(
                name=province_name, defaults={"sort_order": p_order}
            )
            for city_name, districts in cities.items():
                city, _ = City.objects.update_or_create(
                    province=province,
                    name=city_name,
                    defaults={"is_popular": city_name in {"Libreville", "Port-Gentil", "Franceville"}},
                )
                for district_name in districts:
                    District.objects.update_or_create(city=city, name=district_name)

    def _seed_listings(self):
        User = get_user_model()
        for item in DEMO_LISTINGS:
            user, created = User.objects.get_or_create(
                phone_number=item["phone"],
                defaults={"phone_verified": True},
            )
            profile = user.profile
            city = City.objects.filter(name=item["city"]).first()
            district = District.objects.filter(name=item["district"], city=city).first() if city else None
            profession = Profession.objects.filter(name=item["job"]).first()
            profile.display_name = item["author_name"]
            profile.show_whatsapp = True
            profile.whatsapp_number = item["phone"]
            profile.city = city
            profile.district = district
            profile.looking_for = f"Je recherche un(e) {item['job'].split('/')[0].strip().lower()}"
            profile.bio = (
                f"Bonjour, je suis {item['author_name']}. "
                "J'utilise Fallaman pour trouver rapidement de la main-d'œuvre fiable près de chez moi."
            )
            profile.availability = "flexible"
            profile.save()
            listing, created = Listing.objects.get_or_create(
                author=user,
                title=f"Recherche {item['job'].split('/')[0].strip().lower()}",
                defaults={
                    "listing_type": item["type"],
                    "profession": profession,
                    "description": item["description"],
                    "province": city.province if city else None,
                    "city": city,
                    "district": district,
                    "salary_type": item["salary_type"],
                    "salary_amount": item["salary"],
                    "duration": item["duration"],
                    "availability": Listing.Availability.IMMEDIATE,
                },
            )
            if created or listing.status != Listing.Status.PUBLISHED:
                listing.publish()

    def _seed_test_accounts(self):
        User = get_user_model()
        libreville = City.objects.filter(name="Libreville").first()
        angondje = (
            District.objects.filter(name="Angondjé", city=libreville).first() if libreville else None
        )
        nounou = Profession.objects.filter(name="Nounou").first()
        macon = Profession.objects.filter(name="Maçon").first()

        accounts = [
            {
                "phone": "+24106111111",
                "password": getattr(settings, "DEMO_STAFF_PASSWORD", "") or None,
                "email": "admin@fallaman.test",
                "is_staff": True,
                "is_superuser": True,
                "display_name": "Admin Fallaman",
                "bio": "Compte administrateur pour les tests et la modération.",
                "looking_for": "",
                "profession": None,
                "label": "Admin",
            },
            {
                "phone": "+24106222222",
                "password": DEMO_MEMBER_PASSWORD,
                "email": "marie@fallaman.test",
                "is_staff": False,
                "is_superuser": False,
                "display_name": "Marie Chercheuse",
                "bio": "Je cherche un emploi stable à Libreville. Disponible immédiatement.",
                "looking_for": "Emploi : nounou, femme de ménage ou aide à domicile",
                "profession": nounou,
                "years": 4,
                "availability": "immediate",
                "label": "Chercheur d'emploi",
            },
            {
                "phone": "+24106333333",
                "password": DEMO_MEMBER_PASSWORD,
                "email": "paul@fallaman.test",
                "is_staff": False,
                "is_superuser": False,
                "display_name": "Paul Employeur",
                "bio": "Je publie des offres pour trouver rapidement de la main-d'œuvre à Libreville.",
                "looking_for": "Main-d'œuvre : maçon, chauffeur, débroussailleur",
                "profession": macon,
                "years": None,
                "availability": "flexible",
                "label": "Employeur",
            },
        ]

        for item in accounts:
            user, created = User.objects.get_or_create(
                phone_number=item["phone"],
                defaults={
                    "phone_verified": True,
                    "is_staff": item["is_staff"],
                    "is_superuser": item["is_superuser"],
                },
            )
            user.phone_verified = True
            user.is_staff = item["is_staff"]
            user.is_superuser = item["is_superuser"]
            user.is_active = True
            user.email = item.get("email", "")
            user.email_verified = bool(user.email)
            if item["password"]:
                user.set_password(item["password"])
            else:
                user.set_unusable_password()
            user.save()

            profile = user.profile
            profile.display_name = item["display_name"]
            profile.bio = item["bio"]
            profile.looking_for = item["looking_for"]
            profile.city = libreville
            profile.district = angondje
            profile.primary_profession = item["profession"]
            profile.years_of_experience = item.get("years")
            profile.availability = item.get("availability") or ""
            profile.whatsapp_number = item["phone"]
            profile.show_whatsapp = True
            profile.is_public = True
            profile.save()
            self.stdout.write(f"  Compte test {item['label']}: {item['phone']}")
