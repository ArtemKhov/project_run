from django.db.models import Min, Max
from geopy.distance import geodesic
from .models import CollectibleItem, Position


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


def calculate_position_distance(position):
    """
    Рассчитывает накопленное расстояние для новой позиции в километрах.
    Вызывается при создании каждой новой позиции.
    """
    previous_position = Position.objects.filter(run=position.run, id__lt=position.id).order_by('-id').first()

    if previous_position:
        current_point = (float(position.latitude), float(position.longitude))
        previous_point = (float(previous_position.latitude), float(previous_position.longitude))
        segment_distance_km = geodesic(previous_point, current_point).kilometers

        total_distance_km = round(previous_position.distance + segment_distance_km, 2)
        position.distance = total_distance_km
    else:
        position.distance = 0.0

    return position


def calculate_position_speed(position):
    """
    Рассчитывает скорость для новой позиции в метрах в секунду.
    Вызывается при создании каждой новой позиции.
    """
    previous_position = Position.objects.filter(run=position.run, id__lt=position.id).order_by('-id').first()

    if previous_position:
        current_point = (float(position.latitude), float(position.longitude))
        previous_point = (float(previous_position.latitude), float(previous_position.longitude))
        segment_distance_km = geodesic(previous_point, current_point).kilometers

        # Рассчитываем скорость в м/с
        time_diff = (position.date_time - previous_position.date_time).total_seconds()
        if time_diff > 0:
            # Преобразуем км в метры и делим на секунды
            speed_mps = (segment_distance_km * 1000) / time_diff
            position.speed = round(speed_mps, 2)
        else:
            position.speed = 0.0
    else:
        position.speed = 0.0

    return position


def calculate_average_speed(positions_queryset):
    """
    Рассчитывает среднюю скорость забега по всем позициям в м/с.
    """
    positions = positions_queryset.order_by('id')
    if positions.count() <= 1:
        return 0.0

    total_distance_km = 0.0
    prev_point = None

    # Рассчитываем общее расстояние
    for position in positions:
        current_point = (float(position.latitude), float(position.longitude))
        if prev_point:
            segment_distance_km = geodesic(prev_point, current_point).kilometers
            total_distance_km += segment_distance_km
        prev_point = current_point

    # Рассчитываем общее время
    time_aggregates = positions.aggregate(
        min_time=Min('date_time'),
        max_time=Max('date_time')
    )

    min_time = time_aggregates['min_time']
    max_time = time_aggregates['max_time']

    if min_time and max_time and min_time != max_time:
        total_time_seconds = (max_time - min_time).total_seconds()
        if total_time_seconds > 0:
            # Средняя скорость = общее расстояние (в метрах) / общее время (в секундах)
            average_speed_mps = (total_distance_km * 1000) / total_time_seconds
            return round(average_speed_mps, 2)

    return 0.0