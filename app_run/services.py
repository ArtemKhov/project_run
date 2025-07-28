from geopy.distance import geodesic
from .models import CollectibleItem

def check_and_collect_items(position, athlete):
    """
    Проверяет, находится ли позиция бегуна в радиусе 100 м от любого CollectibleItem (предмета).
    Если да — добавляет атлета в список собравших этот предмет.
    """
    runner_point = (float(position.latitude), float(position.longitude))

    for item in CollectibleItem.objects.all():
        item_point = (float(item.latitude), float(item.longitude))
        distance = geodesic(runner_point, item_point).meters
        if distance <= 100:
            item.users.add(athlete)