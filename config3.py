import xml.etree.ElementTree as ET  # для парсинга XML
import sys  # для аргументов командной строки
import os  # для работы с файловой системой
import urllib.request  # для HTTP запросов
import urllib.error  # для обработки ошибок HTTP
import gzip  # для распаковки gzip
import tarfile  # для работы с tar архивами
from io import BytesIO  # для работы с бинарными данными в памяти

# Кеш для APKINDEX
APKINDEX_CACHE = None  # Глобальная переменная для кеширования содержимого APKINDEX
APKINDEX_URL = None  # Глобальная переменная для хранения URL последнего загруженного APKINDEX

# Глобальные структуры данных для графа
dependency_graph = {}  # хранит граф: пакет -> список зависимостей
visited = set()  # отслеживает полностью обработанные пакеты
visiting = set()  # отслеживает пакеты в текущей цепочке (для обнаружения циклов)


def parse_config(config_path):
    """Парсит конфигурационный файл XML и возвращает параметры"""
    try:
        # Проверки валидности файла
        if not os.path.exists(config_path):  # Проверка существования файла
            raise FileNotFoundError(f"Конфигурационный файл не найден: {config_path}")
        if not os.path.isfile(config_path):  # Проверка что это файл
            raise ValueError(f"Указанный путь не является файлом: {config_path}")
        if not config_path.lower().endswith('.xml'):  # Проверка расширения
            raise ValueError(f"Файл должен иметь расширение .xml: {config_path}")

        tree = ET.parse(config_path)  # Парсинг XML файла
        root = tree.getroot()  # Получение корневого элемента
        config = {}  # Инициализация словаря конфигурации

        # Извлечение имени пакета
        package_name_elem = root.find('package_name')  # Поиск элемента package_name
        if package_name_elem is None:  # Проверка наличия элемента
            raise ValueError("Отсутствует обязательный элемент: package_name")
        if package_name_elem.text is None:  # Проверка что элемент не пустой
            raise ValueError("Элемент package_name не может быть пустым")
        package_name = package_name_elem.text.strip()  # Очистка и получение текста
        if not package_name:  # Проверка на пустую строку
            raise ValueError("Имя пакета не может быть пустой строкой")
        if not all(c.isalnum() or c in ['-', '_', '.'] for c in package_name):  # Валидация символов
            raise ValueError(f"Недопустимые символы в имени пакета: {package_name}")
        config['package_name'] = package_name  # Сохранение в конфиг

        # Извлечение URL репозитория
        repository_url_elem = root.find('repository_url')  # Поиск элемента repository_url
        if repository_url_elem is None:  # Проверка наличия элемента
            raise ValueError("Отсутствует обязательный элемент: repository_url")
        if repository_url_elem.text is None:  # Проверка что элемент не пустой
            raise ValueError("Элемент repository_url не может быть пустым")
        repository_url = repository_url_elem.text.strip()  # Очистка и получение текста
        if not repository_url:  # Проверка на пустую строку
            raise ValueError("URL репозитория не может быть пустой строкой")
        config['repository_url'] = repository_url  # Сохранение в конфиг

        # Извлечение режима тестового репозитория
        test_repo_mode_elem = root.find('test_repo_mode')  # Поиск элемента test_repo_mode
        if test_repo_mode_elem is not None and test_repo_mode_elem.text:  # Проверка наличия и содержимого
            test_repo_mode = test_repo_mode_elem.text.strip().lower()  # Очистка и приведение к нижнему регистру
            valid_modes = ['true', 'false', 'local', 'remote']  # Допустимые значения
            if test_repo_mode not in valid_modes:  # Проверка валидности значения
                raise ValueError(f"Недопустимый режим работы: {test_repo_mode}")
            config['test_repo_mode'] = test_repo_mode  # Сохранение в конфиг
        else:
            config['test_repo_mode'] = 'false'  # Значение по умолчанию

        # Извлечение версии пакета
        package_version_elem = root.find('package_version')  # Поиск элемента package_version
        if package_version_elem is not None and package_version_elem.text:  # Проверка наличия и содержимого
            package_version = package_version_elem.text.strip()  # Очистка текста
            if not package_version:  # Проверка на пустую строку
                raise ValueError("Версия пакета не может быть пустой строкой")
            config['package_version'] = package_version  # Сохранение в конфиг
        else:
            config['package_version'] = '1.0.0'  # Значение по умолчанию

        # Извлечение настройки ASCII вывода
        ascii_tree_output_elem = root.find('ascii_tree_output')  # Поиск элемента ascii_tree_output
        if ascii_tree_output_elem is not None and ascii_tree_output_elem.text:  # Проверка наличия и содержимого
            ascii_text = ascii_tree_output_elem.text.strip().lower()  # Очистка и приведение к нижнему регистру
            valid_boolean_values = ['true', 'false', '1', '0', 'yes', 'no']  # Допустимые булевы значения
            if ascii_text not in valid_boolean_values:  # Проверка валидности значения
                raise ValueError(f"Недопустимое значение для ascii_tree_output: {ascii_tree_output_elem.text}")
            config['ascii_tree_output'] = ascii_text in ['true', '1', 'yes']  # Преобразование в булево значение
        else:
            config['ascii_tree_output'] = False  # Значение по умолчанию

        return config  # Возврат конфигурации

    except ET.ParseError as e:  # Обработка ошибок парсинга XML
        raise ValueError(f"Ошибка парсинга XML: {e}")
    except FileNotFoundError as e:  # Обработка ошибок файла
        raise ValueError(f"Файл не найден: {e}")
    except PermissionError as e:  # Обработка ошибок прав доступа
        raise ValueError(f"Отсутствуют права доступа к файлу: {e}")
    except Exception as e:  # Обработка всех остальных ошибок
        raise ValueError(f"Неожиданная ошибка при загрузке конфигурации: {e}")


def download_and_parse_apkindex(repository_url):
    """Скачивает и парсит APKINDEX.tar.gz с кешированием"""
    global APKINDEX_CACHE, APKINDEX_URL  # Объявление глобальных переменных для кеширования

    if APKINDEX_URL == repository_url and APKINDEX_CACHE is not None:  # Проверка кеша
        return APKINDEX_CACHE  # Возврат кешированных данных

    try:
        if repository_url.endswith('/'):  # Проверка завершается ли URL слешем
            apkindex_url = repository_url + 'APKINDEX.tar.gz'  # Формирование URL без дополнительного слеша
        else:
            apkindex_url = repository_url + '/APKINDEX.tar.gz'  # Формирование URL с добавлением слеша

        print(f"Скачиваем {apkindex_url}...")  # Сообщение о начале загрузки

        with urllib.request.urlopen(apkindex_url) as response:  # HTTP-запрос к репозиторию
            apkindex_data = response.read()  # Чтение бинарных данных

        print("Файл скачан, распаковываем...")  # Сообщение о начале распаковки

        with gzip.GzipFile(fileobj=BytesIO(apkindex_data)) as gz_file:  # Распаковка gzip
            tar_data = gz_file.read()  # Чтение распакованных tar-данных

        with tarfile.open(fileobj=BytesIO(tar_data)) as tar:  # Открытие tar-архива
            apkindex_file = tar.extractfile('APKINDEX')  # Извлечение файла APKINDEX из архива
            apkindex_content = apkindex_file.read().decode('utf-8')  # Чтение и декодирование содержимого

        APKINDEX_CACHE = apkindex_content  # Сохранение в кеш
        APKINDEX_URL = repository_url  # Сохранение URL в кеш

        return apkindex_content  # Возврат распарсенного содержимого

    except Exception as e:  # Обработка всех исключений
        raise ValueError(f"Ошибка при загрузке APKINDEX: {e}")  # Преобразование в ValueError с сообщением


def get_all_packages_from_apkindex(repository_url):
    """Получает список всех пакетов из APKINDEX"""
    apkindex_content = download_and_parse_apkindex(repository_url)  # Загрузка и парсинг APKINDEX
    lines = apkindex_content.split('\n')  # Разделение содержимого на строки

    packages = []  # Инициализация списка пакетов
    current_package = None  # Переменная для текущего пакета

    for line in lines:  # Цикл по всем строкам APKINDEX
        if line.startswith('P:'):  # Если строка содержит имя пакета
            current_package = line[2:]  # Извлечение имени пакета (после 'P:')
            if current_package and current_package not in packages:  # Если пакет не пустой и еще не в списке
                packages.append(current_package)  # Добавление пакета в список

    return packages  # Возврат списка всех уникальных пакетов


def get_all_packages_from_test_file(test_repo_path):
    """Получает список всех пакетов из тестового файла"""
    try:
        if not os.path.exists(test_repo_path):  # Проверка существования файла
            raise ValueError(f"Тестовый файл не найден: {test_repo_path}")  # Ошибка если файл не найден

        with open(test_repo_path, 'r', encoding='utf-8') as f:  # Открытие файла для чтения
            content = f.read()  # Чтение всего содержимого файла

        packages = []  # Инициализация списка пакетов
        for line in content.split('\n'):  # Цикл по всем строкам файла
            line = line.strip()  # Удаление пробелов в начале и конце
            if line and ':' in line and not line.startswith('#'):  # Проверка на валидную строку (не пустая, содержит :, не комментарий)
                pkg = line.split(':', 1)[0].strip()  # Извлечение имени пакета до двоеточия
                if pkg and pkg not in packages:  # Если имя не пустое и еще не в списке
                    packages.append(pkg)  # Добавление пакета в список

        return packages  # Возврат списка всех пакетов

    except Exception as e:  # Обработка всех исключений
        raise ValueError(f"Ошибка чтения тестового файла: {e}")  # Преобразование исключения в ValueError


def find_package_dependencies(apkindex_content, package_name, package_version):
    """Ищет зависимости пакета в APKINDEX"""
    lines = apkindex_content.split('\n')  # Разделяем содержимое на строки
    current_package = None  # Текущий обрабатываемый пакет
    in_target_package = False  # Флаг нахождения в целевом пакете
    dependencies = []  # Список зависимостей

    for line in lines:  # Цикл по всем строкам APKINDEX
        if line.startswith('P:'):  # Если строка с именем пакета
            current_package = line[2:]  # Извлекаем имя пакета
            in_target_package = (current_package == package_name)  # Проверяем совпадение с искомым

        elif line.startswith('V:'):  # Если строка с версией пакета
            if in_target_package and package_version and line[2:] != package_version:  # Проверяем версию
                in_target_package = False  # Сбрасываем флаг если версия не совпадает

        elif line.startswith('D:') and in_target_package:  # Если строка с зависимостями и мы в целевом пакете
            deps_line = line[2:]  # Извлекаем строку зависимостей
            if deps_line:  # Если зависимости есть
                dependencies = [dep.strip() for dep in deps_line.split() if dep.strip()]  # Разделяем и очищаем
                break  # Прерываем цикл после нахождения зависимостей

    return dependencies  # Возвращаем найденные зависимости


def read_dependencies_from_test_file(package_name, test_repo_path):
    """Читает зависимости из тестового файла (для тестового режима)"""
    try:
        if not os.path.exists(test_repo_path):  # Проверка существования файла
            raise ValueError(f"Тестовый файл не найден: {test_repo_path}")  # Ошибка если файл не найден

        with open(test_repo_path, 'r', encoding='utf-8') as f:  # Открытие файла для чтения
            content = f.read()  # Чтение всего содержимого файла

        for line in content.split('\n'):  # Цикл по всем строкам файла
            line = line.strip()  # Удаление пробелов в начале и конце
            if line and ':' in line and not line.startswith('#'):  # Проверка на валидную строку (не пустая, содержит :, не комментарий)
                pkg, deps_str = line.split(':', 1)  # Разделение строки на имя пакета и зависимости
                pkg = pkg.strip()  # Очистка имени пакета от пробелов
                if pkg == package_name:  # Если нашли нужный пакет
                    dependencies = [dep.strip() for dep in deps_str.split(',') if dep.strip()]  # Разделение зависимостей по запятым и очистка
                    return dependencies  # Возврат списка зависимостей

        return []  # Возврат пустого списка если пакет не найден

    except Exception as e:  # Обработка всех исключений
        raise ValueError(f"Ошибка чтения тестового файла: {e}")  # Преобразование исключения в ValueError


def get_package_dependencies(package_name, package_version, repository_url, is_test_mode):
    """Универсальная функция для получения зависимостей"""
    if is_test_mode:  # Проверка режима работы
        return read_dependencies_from_test_file(package_name, repository_url)  # Чтение из тестового файла
    else:  # Режим работы с реальным репозиторием
        apkindex_content = download_and_parse_apkindex(repository_url)  # Загрузка и парсинг APKINDEX
        return find_package_dependencies(apkindex_content, package_name, package_version)  # Поиск зависимостей


def build_dependency_graph(package_name, package_version, repository_path, is_test_mode, depth=0, max_depth=10,
                           chain=None):
    """Рекурсивно строит граф зависимостей для одного пакета"""
    if chain is None:  # Если цепочка не передана
        chain = []  # Инициализируем пустым списком

    if depth > max_depth:  # Проверка максимальной глубины рекурсии
        dependency_graph[package_name] = ["MAX_DEPTH_REACHED"]  # Записываем ошибку глубины
        return  # Прерываем рекурсию

    if package_name in visiting:  # Обнаружение циклической зависимости
        current_chain = chain + [package_name]  # Формируем текущую цепочку
        cycle_start = current_chain.index(package_name)  # Находим начало цикла
        cycle_part = current_chain[cycle_start:]  # Выделяем циклическую часть
        cycle_chain = " → ".join(cycle_part)  # Форматируем цикл в строку
        dependency_graph[package_name] = ["CYCLE: " + cycle_chain]  # Записываем информацию о цикле
        return  # Прерываем рекурсию

    if package_name in visited:  # Если пакет уже обработан
        return  # Выходим из функции

    visiting.add(package_name)  # Добавляем пакет в текущую цепочку
    current_chain = chain + [package_name]  # Обновляем текущую цепочку

    try:
        dependencies = get_package_dependencies(package_name, package_version, repository_path, is_test_mode)  # Получаем зависимости
        dependency_graph[package_name] = dependencies  # Сохраняем зависимости в граф

        for dep in dependencies:  # Рекурсивно обрабатываем каждую зависимость
            build_dependency_graph(dep, None, repository_path, is_test_mode, depth + 1, max_depth, current_chain)

    except Exception as e:  # Обработка ошибок
        dependency_graph[package_name] = ["ERROR: " + str(e)]  # Сохраняем ошибку

    finally:  # Выполняется всегда
        visiting.remove(package_name)  # Удаляем пакет из текущей цепочки
        visited.add(package_name)  # Добавляем пакет в обработанные


def build_complete_dependency_graph(repository_url, is_test_mode):
    """Строит полный граф всех пакетов в репозитории"""
    print("\nПостроение полного графа зависимостей...")  # Сообщение о начале построения

    if is_test_mode:  # Если тестовый режим
        all_packages = get_all_packages_from_test_file(repository_url)  # Получаем пакеты из тестового файла
        print(f"Найдено пакетов в тестовом файле: {len(all_packages)}")  # Вывод количества пакетов
    else:  # Если рабочий режим
        all_packages = get_all_packages_from_apkindex(repository_url)  # Получаем пакеты из APKINDEX
        print(f"Найдено пакетов в репозитории: {len(all_packages)}")  # Вывод количества пакетов

    total_packages = len(all_packages)  # Сохраняем общее количество пакетов

    # Убираем поштучный вывод, оставляем только общий прогресс
    for package in all_packages:  # Цикл по всем пакетам
        if package not in visited:  # Если пакет еще не обработан
            build_dependency_graph(package, None, repository_url, is_test_mode)  # Строим граф для пакета

    print(f"Обработано пакетов: {len(visited)}/{total_packages}")  # Вывод прогресса обработки
    print("Полный граф построен!")  # Сообщение о завершении

def display_dependency_graph():
    """Выводит построенный граф зависимостей"""
    print("\n" + "=" * 60)  # Верхняя разделительная линия
    print("ПОЛНЫЙ ГРАФ ЗАВИСИМОСТЕЙ РЕПОЗИТОРИЯ")  # Заголовок
    print("=" * 60)  # Нижняя разделительная линия

    # Сортируем пакеты для удобства чтения
    sorted_packages = sorted(dependency_graph.keys())  # Сортировка имен пакетов

    for package in sorted_packages:  # Цикл по всем пакетам
        dependencies = dependency_graph[package]  # Получение зависимостей пакета
        if dependencies:  # Если зависимости есть
            deps_str = ", ".join(dependencies)  # Формирование строки зависимостей
            print(f"{package} -> [{deps_str}]")  # Вывод пакета с зависимостями
        else:  # Если зависимостей нет
            print(f"{package} -> []")  # Вывод пакета без зависимостей

    print(f"\nВсего пакетов в графе: {len(dependency_graph)}")  # Вывод общего количества пакетов

def create_test_files():
    """Создает тестовые файлы для демонстрации"""
    test_files = {
        "test_simple.txt": """A: B, C
B: D
C: E
D: 
E: F
F:""",

        "test_cycle.txt": """A: B
B: C  
C: A
D: E
E:""",

        "test_diamond.txt": """A: B, C
B: D
C: D
D: E
E:""",

        "test_complex.txt": """A: B, C, F
B: D, E
C: G
D: H
E: H, I
F: J
G: K
H: 
I: J
J: 
K: L
L:"""
    }

    for filename, content in test_files.items():  # Цикл по всем тестовым файлам
        if not os.path.exists(filename):  # Проверка существования файла
            with open(filename, 'w', encoding='utf-8') as f:  # Открытие файла для записи
                f.write(content)  # Запись содержимого в файл
            print(f"Создан тестовый файл: {filename}")  # Сообщение о создании файла


def interactive_test_mode():
    """Интерактивный режим тестирования"""
    print("\n" + "=" * 50)  # Разделительная линия
    print("ИНТЕРАКТИВНЫЙ РЕЖИМ ТЕСТИРОВАНИЯ")  # Заголовок
    print("=" * 50)  # Разделительная линия

    while True:  # Бесконечный цикл для ввода пути
        file_path = input("\nВведите путь к тестовому файлу (например: test_simple.txt): ").strip()  # Запрос пути

        if not file_path:  # Проверка пустого ввода
            print("Путь не может быть пустым!")  # Сообщение об ошибке
            continue  # Повтор запроса

        if not file_path.endswith('.txt'):  # Проверка расширения
            file_path += '.txt'  # Добавление расширения .txt

        if os.path.exists(file_path):  # Проверка существования файла
            break  # Выход из цикла если файл найден
        else:
            print(f"Файл '{file_path}' не найден!")  # Сообщение об ошибке
            create_test_files()  # Создание тестовых файлов
            print("Доступные тестовые файлы:")  # Вывод списка файлов
            for file in ["test_simple.txt", "test_cycle.txt", "test_diamond.txt", "test_complex.txt"]:  # Цикл по файлам
                if os.path.exists(file):  # Проверка существования файла
                    print(f"  - {file}")  # Вывод имени файла

    print(f"\nАнализируем файл {file_path}...")  # Сообщение о начале анализа

    # Очищаем глобальные структуры
    dependency_graph.clear()  # Очистка графа зависимостей
    visited.clear()  # Очистка посещенных пакетов
    visiting.clear()  # Очистка текущей цепочки
    global APKINDEX_CACHE, APKINDEX_URL  # Объявление глобальных переменных
    APKINDEX_CACHE = None  # Сброс кеша APKINDEX
    APKINDEX_URL = None  # Сброс URL APKINDEX

    # Строим полный граф
    build_complete_dependency_graph(file_path, True)  # Построение графа в тестовом режиме
    display_dependency_graph()  # Вывод графа зависимостей


def main():
    """Основная функция приложения"""
    if len(sys.argv) < 2:  # Проверяем количество аргументов
        print("Использование:")  # Выводим справку
        print("  python main.py <config.xml>    - режим с конфигурационным файлом")
        print("  python main.py --interactive   - интерактивный тестовый режим")
        sys.exit(1)  # Выход с ошибкой

    if sys.argv[1] == "--interactive":  # Если запрошен интерактивный режим
        interactive_test_mode()  # Запускаем интерактивный режим
    else:
        config_path = sys.argv[1]  # Получаем путь к конфигурационному файлу
        try:
            # Этап 1: Загрузка конфигурации
            config = parse_config(config_path)  # Парсим конфигурационный файл

            create_test_files()  # Создаем тестовые файлы

            # Этап 2: Построение полного графа зависимостей

            # Очищаем глобальные структуры
            dependency_graph.clear()  # Очищаем граф зависимостей
            visited.clear()  # Очищаем посещенные пакеты
            visiting.clear()  # Очищаем текущую цепочку
            global APKINDEX_CACHE, APKINDEX_URL  # Объявляем глобальные переменные
            APKINDEX_CACHE = None  # Сбрасываем кеш APKINDEX
            APKINDEX_URL = None  # Сбрасываем URL APKINDEX

            # Определяем режим работы
            is_test_mode = config['test_repo_mode'] in ['true', 'local']  # Проверяем тестовый режим

            # Строим полный граф
            build_complete_dependency_graph(  # Запускаем построение графа
                config['repository_url'],  # Передаем URL репозитория
                is_test_mode  # Передаем режим работы
            )

            display_dependency_graph()  # Выводим граф зависимостей

        except ValueError as e:  # Обрабатываем ошибки валидации
            print(f"Ошибка: {e}")  # Выводим сообщение об ошибке
            sys.exit(1)  # Выход с ошибкой
        except Exception as e:  # Обрабатываем все остальные ошибки
            print(f"Неожиданная ошибка: {e}")  # Выводим сообщение об ошибке
            sys.exit(1)  # Выход с ошибкой

if __name__ == "__main__":
    main()
