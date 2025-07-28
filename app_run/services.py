from django.db.models import Min, Max
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

def calculate_run_distance(positions_queryset):
    """
    Рассчитывает общую дистанцию забега в километрах по цепочке позиций.
    Использует геодезическое расстояние между соседними точками.
    """
    positions = positions_queryset.order_by('id')
    total_distance = 0.0
    prev_point = None

    for position in positions:
        current_point = (float(position.latitude), float(position.longitude))
        if prev_point:
            segment_distance = geodesic(prev_point, current_point).kilometers
            total_distance += segment_distance
        prev_point = current_point

    return round(total_distance, 3)

def calculate_run_time_seconds(positions_queryset):
    """
    Рассчитывает общее время забега в секундах по позициям.
    Использует min и max date_time, чтобы учесть офлайн-записи.
    """
    time_aggregates = positions_queryset.aggregate(
        min_time=Min('date_time'),
        max_time=Max('date_time')
    )

    min_time = time_aggregates['min_time']
    max_time = time_aggregates['max_time']

    if min_time and max_time:
        return int((max_time - min_time).total_seconds())
    return 0