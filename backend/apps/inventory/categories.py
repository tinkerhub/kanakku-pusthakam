DEFAULT_CATEGORIES = [
    "SBCs",
    "Microcontrollers",
    "Microprocessors",
    "Sensors",
    "Actuators",
    "Cables",
    "Accessories",
]


def ensure_default_categories(makerspace):
    from django.utils.text import slugify

    from apps.inventory.models import Category

    for order, name in enumerate(DEFAULT_CATEGORIES):
        Category.objects.get_or_create(
            makerspace=makerspace,
            slug=slugify(name),
            defaults={"name": name, "display_order": order},
        )
