from django.conf import settings
from django.core.management.base import BaseCommand

from apps.accounts.models import User
from apps.apiclients.models import ApiClient
from apps.inventory.categories import ensure_default_categories
from apps.inventory.models import Category, InventoryProduct, PublicAvailabilityMode
from apps.makerspaces.models import Makerspace


class Command(BaseCommand):
    help = "Seed an idempotent demo makerspace and public inventory."

    def handle(self, *args, **options):
        superadmin, user_created = User.objects.get_or_create(
            username="superadmin",
            defaults={
                "email": "superadmin@makerspace.local",
                "role": User.Role.SUPERADMIN,
                "is_staff": True,
                "is_superuser": True,
            },
        )
        if user_created:
            superadmin.set_unusable_password()
            superadmin.save(update_fields=["password"])

        makerspace = Makerspace.objects.filter(slug="makerspace").first()
        makerspace_created = False
        if makerspace is None:
            makerspace = Makerspace.objects.filter(slug="tinkerspace").first()
            if makerspace is None:
                makerspace = Makerspace.objects.create(
                    slug="makerspace",
                    name="Makerspace Demo",
                    public_inventory_enabled=True,
                    created_by=superadmin,
                )
                makerspace_created = True
            else:
                makerspace.slug = "makerspace"

        makerspace.name = "Makerspace Demo"
        makerspace.public_inventory_enabled = True
        makerspace.save(update_fields=["slug", "name", "public_inventory_enabled"])
        ensure_default_categories(makerspace)

        products = [
            {
                "name": "Soldering Iron",
                "public_availability_mode": PublicAvailabilityMode.EXACT_COUNT,
                "show_public_count": True,
                "total_quantity": 10,
                "available_quantity": 8,
                "storage_location": "Electronics Bench A",
            },
            {
                "name": "Arduino Uno",
                "public_availability_mode": PublicAvailabilityMode.EXACT_COUNT,
                "show_public_count": False,
                "total_quantity": 20,
                "available_quantity": 2,
            },
            {
                "name": "3D Printer Filament",
                "public_availability_mode": PublicAvailabilityMode.STATUS_ONLY,
                "total_quantity": 50,
                "available_quantity": 50,
                "storage_location": "Fabrication Storage",
            },
            {
                "name": "Oscilloscope",
                "public_availability_mode": PublicAvailabilityMode.STATUS_ONLY,
                "total_quantity": 4,
                "available_quantity": 0,
            },
            {
                "name": "Raspberry Pi 5",
                "public_availability_mode": PublicAvailabilityMode.STATUS_ONLY,
                "total_quantity": 15,
                "available_quantity": 3,
            },
            {
                "name": "Secret Internal Tool",
                "is_public": False,
                "total_quantity": 1,
                "available_quantity": 1,
                "storage_location": "Admin Cabinet",
            },
            {
                "name": "Retired Heat Gun",
                "is_archived": True,
                "is_public": True,
                "total_quantity": 2,
                "available_quantity": 2,
            },
        ]

        created_count = 0
        for product_data in products:
            _, created = InventoryProduct.objects.get_or_create(
                makerspace=makerspace,
                name=product_data["name"],
                defaults=product_data,
            )
            created_count += int(created)

        product_categories = {
            "Arduino Uno": "microcontrollers",
            "Raspberry Pi 5": "sbcs",
            "Soldering Iron": "accessories",
            "Oscilloscope": "accessories",
            "3D Printer Filament": "accessories",
        }
        categories = {
            category.slug: category
            for category in Category.objects.filter(
                makerspace=makerspace,
                slug__in=set(product_categories.values()),
            )
        }
        for product_name, category_slug in product_categories.items():
            product = InventoryProduct.objects.get(
                makerspace=makerspace,
                name=product_name,
            )
            if product.category_id is None:
                product.category = categories[category_slug]
                product.save(update_fields=["category"])

        # review fix #3: do NOT use get_or_create - secret_encrypted is non-null with no default,
        # so a create() without it would crash. Fetch-or-instantiate, then set the secret.
        if settings.HMAC_CLIENT_ID and settings.HMAC_SECRET:
            client = ApiClient.objects.filter(client_id=settings.HMAC_CLIENT_ID).first()
            if client is None:
                client = ApiClient(client_id=settings.HMAC_CLIENT_ID, label="Legacy frontend")
            client.allowed_origins = list(settings.CORS_ALLOWED_ORIGINS)
            client.set_secret(settings.HMAC_SECRET)
            client.save()

        self.stdout.write(
            self.style.SUCCESS(
                "Seeded demo data: "
                f"user_created={user_created}, "
                f"makerspace_created={makerspace_created}, "
                f"products_created={created_count}."
            )
        )
