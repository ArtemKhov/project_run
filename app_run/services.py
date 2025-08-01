# Standard library imports
from django.db.models import Min, Max

# Third-party imports
from geopy.distance import geodesic

# Local imports
from .models import CollectibleItem, Position, Challenge


def check_and_collect_items(position, athlete):
    """
    Проверяет, находится ли позиция бегуна в радиусе 100 м от любого CollectibleItem (предмета).
    Если да — добавляет атлета в список собравших этот предмет.
    
    Args:
        position: Объект Position - текущая позиция бегуна
        athlete: Объект User - атлет, который может собрать предмет
    
    Returns:
        None - функция изменяет связанные объекты в базе данных
    """
    # Получаем координаты позиции бегуна
    runner_point = (float(position.latitude), float(position.longitude))

    # Проверяем все доступные коллекционные предметы
    for item in CollectibleItem.objects.all():
        item_point = (float(item.latitude), float(item.longitude))
        distance = geodesic(runner_point, item_point).meters
        
        # Если расстояние <= 100 метров, добавляем атлета к предмету
        if distance <= 100:
            item.users.add(athlete)


def calculate_run_distance(positions_queryset):
    """
    Рассчитывает общую дистанцию забега в километрах по цепочке позиций.
    Использует геодезическое расстояние между соседними точками.
    
    Args:
        positions_queryset: QuerySet позиций забега
        
    Returns:
        float: Общая дистанция забега в километрах, округленная до 3 знаков
    """
    positions = positions_queryset.order_by('id')
    total_distance = 0.0
    prev_point = None

    # Проходим по всем позициям и суммируем расстояния между соседними точками
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
    
    Args:
        positions_queryset: QuerySet позиций забега
        
    Returns:
        int: Общее время забега в секундах
    """
    # Получаем минимальное и максимальное время из всех позиций
    time_aggregates = positions_queryset.aggregate(
        min_time=Min('date_time'),
        max_time=Max('date_time')
    )

    min_time = time_aggregates['min_time']
    max_time = time_aggregates['max_time']

    # Вычисляем разность времени в секундах
    if min_time and max_time:
        return int((max_time - min_time).total_seconds())
    return 0


def calculate_position_distance(position):
    """
    Рассчитывает накопленное расстояние для новой позиции в километрах.
    Вызывается при создании каждой новой позиции.
    
    Args:
        position: Объект Position - новая позиция
        
    Returns:
        Position: Обновленный объект позиции с рассчитанным расстоянием
    """
    # Получаем предыдущую позицию в том же забеге
    previous_position = Position.objects.filter(run=position.run, id__lt=position.id).order_by('-id').first()

    if previous_position:
        # Рассчитываем расстояние от предыдущей позиции до текущей
        current_point = (float(position.latitude), float(position.longitude))
        previous_point = (float(previous_position.latitude), float(previous_position.longitude))
        segment_distance_km = geodesic(previous_point, current_point).kilometers

        # Добавляем к накопленному расстоянию
        total_distance_km = round(previous_position.distance + segment_distance_km, 2)
        position.distance = total_distance_km
    else:
        # Если это первая позиция, расстояние = 0
        position.distance = 0.0

    return position


def calculate_position_speed(position):
    """
    Рассчитывает скорость для новой позиции в метрах в секунду.
    Вызывается при создании каждой новой позиции.
    
    Args:
        position: Объект Position - новая позиция
        
    Returns:
        Position: Обновленный объект позиции с рассчитанной скоростью
    """
    # Получаем предыдущую позицию в том же забеге
    previous_position = Position.objects.filter(run=position.run, id__lt=position.id).order_by('-id').first()

    if previous_position:
        # Рассчитываем расстояние между позициями
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
        # Если это первая позиция, скорость = 0
        position.speed = 0.0

    return position


def calculate_average_speed(positions_queryset):
    """
    Рассчитывает среднюю скорость забега по всем позициям в м/с.
    
    Args:
        positions_queryset: QuerySet позиций забега
        
    Returns:
        float: Средняя скорость забега в м/с, округленная до 2 знаков
    """
    positions = positions_queryset.order_by('date_time')
    if positions.count() <= 1:
        return 0.0

    # Суммарное расстояние (в километрах)
    total_distance_km = 0.0
    prev_point = None
    for position in positions:
        current_point = (float(position.latitude), float(position.longitude))
        if prev_point:
            segment_distance = geodesic(prev_point, current_point).kilometers
            total_distance_km += segment_distance
        prev_point = current_point

    # Время между первой и последней точкой
    start_time = positions.first().date_time
    end_time = positions.last().date_time
    total_time_seconds = (end_time - start_time).total_seconds()

    # Рассчитываем среднюю скорость
    if total_time_seconds > 0:
        average_speed_mps = (total_distance_km * 1000) / total_time_seconds
        return round(average_speed_mps, 2)
    return 0.0


class ChallengeAssigner:
    """
    Класс для присвоения челленджей атлету по результатам забега.
    
    Анализирует статистику атлета и присваивает соответствующие челленджи
    на основе достигнутых результатов.
    """

    def __init__(self, run, finished_runs_count, total_km, total_distance, run_time_seconds):
        """
        Инициализирует объект ChallengeAssigner.
        
        Args:
            run: Объект Run - текущий забег
            finished_runs_count: int - количество завершенных забегов атлета
            total_km: float - общая дистанция всех забегов атлета в км
            total_distance: float - дистанция текущего забега в км
            run_time_seconds: int - время текущего забега в секундах
        """
        self.run = run
        self.athlete = run.athlete
        self.finished_runs_count = finished_runs_count
        self.total_km = total_km
        self.total_distance = total_distance
        self.run_time_seconds = run_time_seconds

    def assign(self):
        """
        Присваивает все подходящие челленджи атлету по результатам забега.
        
        Проверяет различные условия и создает соответствующие челленджи
        в базе данных, если они еще не существуют.
        """
        self._assign_10_runs()
        self._assign_50_km()
        self._assign_2km_10min()

    def _assign_10_runs(self):
        """
        Присваивает челлендж "Сделай 10 Забегов!", если атлет завершил 10 и более забегов.
        
        Создает челлендж в базе данных, если он еще не существует для данного атлета.
        """
        if self.finished_runs_count >= 10:
            Challenge.objects.get_or_create(
                full_name="Сделай 10 Забегов!",
                athlete=self.athlete,
                defaults={'full_name': "Сделай 10 Забегов!"}
            )

    def _assign_50_km(self):
        """
        Присваивает челлендж "Пробеги 50 километров!", если атлет пробежал >= 50 км.
        
        Создает челлендж в базе данных, если он еще не существует для данного атлета.
        """
        if self.total_km >= 50:
            Challenge.objects.get_or_create(
                full_name="Пробеги 50 километров!",
                athlete=self.athlete,
                defaults={'full_name': "Пробеги 50 километров!"}
            )

    def _assign_2km_10min(self):
        """
        Присваивает челлендж "2 километра за 10 минут!", если дистанция текущего забега >= 2 км и время <= 10 минут.
        
        Создает челлендж в базе данных, если он еще не существует для данного атлета.
        Условие: дистанция >= 2 км И время > 0 секунд И время <= 600 секунд (10 минут)
        """
        if self.total_distance >= 2.0 and self.run_time_seconds > 0 and self.run_time_seconds <= 600:
            Challenge.objects.get_or_create(
                full_name="2 километра за 10 минут!",
                athlete=self.athlete,
                defaults={'full_name': "2 километра за 10 минут!"}
            )