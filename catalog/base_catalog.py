from django.db import transaction

from catalog.models import ItemStatus, ItemType, ProgressCategory

BASE_ITEM_TYPES = [
    "T-shirt",
    "Pantalon",
    "Short",
    "Pull",
    "Veste",
    "Sous-vêtements",
    "Chaussettes",
    "Pyjama",
    "Maillot de bain",
    "Chapeau",
    "Lunettes de soleil",
    "Chaussures",
    "Sandales",
    "Brosse à dents",
    "Dentifrice",
    "Shampoing",
    "Gel douche",
    "Serviette de toilette",
    "Crème solaire",
    "Trousse à pharmacie",
    "Couches",
    "Lingettes",
    "Bavoir",
    "Biberon",
    "Doudou",
    "Passeport",
    "Carte d'identité",
    "Carte vitale",
    "Billets",
    "Chargeur de téléphone",
    "Écouteurs",
    "Livre",
    "Gourde",
    "Sac à dos",
]

BASE_ITEM_STATUSES = [
    ("Pas préparé", "#7b8189", ProgressCategory.NOT_STARTED),
    ("Sorti du placard", "#dcb14f", ProgressCategory.IN_PROGRESS),
    ("Dans les sacs", "#5c8a66", ProgressCategory.DONE),
]


@transaction.atomic
def install_base_catalog(household):
    ItemType.objects.bulk_create(
        ItemType(household=household, name=name) for name in BASE_ITEM_TYPES
    )
    for name, color, progress in BASE_ITEM_STATUSES:
        ItemStatus.objects.create(household=household, name=name, color=color, progress=progress)
