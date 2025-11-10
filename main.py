import xml.etree.ElementTree as ET  # для парсинга XML
import sys  # для аргументов командной строки
import os  # для работы с файловой системой
import urllib.request  # для HTTP запросов
import urllib.error  # для обработки ошибок HTTP
import gzip  # для распаковки gzip
import tarfile  # для работы с tar архивами
from io import BytesIO  # для работы с бинарными данными в памяти

# Глобальные структуры данных для графа
dependency_graph = {}  # хранит граф: пакет -> список зависимостей
visited = set()  # отслеживает полностью обработанные пакеты
visiting = set()  # отслеживает пакеты в текущей цепочке (для обнаружения циклов)


def parse_config(config_path):
    """Парсит конфигурационный файл XML и возвращает параметры"""
    try:
        if not os.path.exists(config_path):  # проверяем существование файла
            raise ValueError(f"Конфигурационный файл не найден: {config_path}")

        tree = ET.parse(config_path)  # парсим XML
        root = tree.getroot()  # получаем корневой элемент

        config = {}  # словарь для хранения конфигурации

        # Имя анализируемого пакета
        package_name_elem = root.find('package_name')  # ищем элемент package_name
        if package_name_elem is None or not package_name_elem.text:  # проверяем наличие
            raise ValueError("Отсутствует обязательный параметр: package_name")
        config['package_name'] = package_name_elem.text  # сохраняем значение

        # URL-адрес репозитория или путь к файлу
        repository_url_elem = root.find('repository_url')  # ищем элемент repository_url
        if repository_url_elem is None or not repository_url_elem.text:  # проверяем наличие
            raise ValueError("Отсутствует обязательный параметр: repository_url")
        config['repository_url'] = repository_url_elem.text  # сохраняем значение

        # Режим работы с тестовым репозиторием
        test_repo_mode_elem = root.find('test_repo_mode')  # ищем элемент test_repo_mode
        if test_repo_mode_elem is not None and test_repo_mode_elem.text:  # если элемент есть
            config['test_repo_mode'] = test_repo_mode_elem.text.lower() == 'true'  # преобразуем в bool
        else:
            config['test_repo_mode'] = False  # значение по умолчанию

        # Версия пакета
        package_version_elem = root.find('package_version')  # ищем элемент package_version
        if package_version_elem is not None and package_version_elem.text:  # если элемент есть
            config['package_version'] = package_version_elem.text  # сохраняем значение
        else:
            config['package_version'] = '1.0.0'  # значение по умолчанию

        # Режим вывода зависимостей в формате ASCII-дерева
        ascii_tree_output_elem = root.find('ascii_tree_output')  # ищем элемент ascii_tree_output
        if ascii_tree_output_elem is not None and ascii_tree_output_elem.text:  # если элемент есть
            config['ascii_tree_output'] = ascii_tree_output_elem.text.lower() == 'true'  # преобразуем в bool
        else:
            config['ascii_tree_output'] = False  # значение по умолчанию

        return config  # возвращаем конфигурацию

    except ET.ParseError as e:  # обработка ошибок парсинга XML
        raise ValueError(f"Ошибка парсинга XML: {e}")
    except Exception as e:  # обработка прочих ошибок
        raise ValueError(f"Ошибка загрузки конфигурации: {e}")


def download_and_parse_apkindex(repository_url):
    """Скачивает и парсит APKINDEX.tar.gz"""
    try:
        # 1. Формируем URL
        if repository_url.endswith('/'):  # если URL заканчивается на /
            apkindex_url = repository_url + 'APKINDEX.tar.gz'  # добавляем без слеша
        else:
            apkindex_url = repository_url + '/APKINDEX.tar.gz'  # добавляем со слешом

        print(f"Скачиваем {apkindex_url}...")

        # 2. Качаем файл
        with urllib.request.urlopen(apkindex_url) as response:  # открываем HTTP соединение
            apkindex_data = response.read()  # читаем все данные

        print("Файл скачан, распаковываем...")

        # 3. Распаковываем .tar.gz
        with gzip.GzipFile(fileobj=BytesIO(apkindex_data)) as gz_file:  # создаем gzip файл в памяти
            tar_data = gz_file.read()  # распаковываем gzip

        # 4. Читаем tar архив
        with tarfile.open(fileobj=BytesIO(tar_data)) as tar:  # открываем tar архив
            # В tar архиве один файл - APKINDEX
            apkindex_file = tar.extractfile('APKINDEX')  # извлекаем файл APKINDEX
            apkindex_content = apkindex_file.read().decode('utf-8')  # читаем и декодируем в строку

        return apkindex_content  # возвращаем содержимое

    except Exception as e:  # обработка всех ошибок
        raise ValueError(f"Ошибка при загрузке APKINDEX: {e}")


def find_package_dependencies(apkindex_content, package_name, package_version):
    """Ищет зависимости пакета в APKINDEX"""
    lines = apkindex_content.split('\n')  # разбиваем содержимое на строки

    current_package = None  # текущий обрабатываемый пакет
    in_target_package = False  # флаг нахождения в целевом пакете
    dependencies = []  # список зависимостей

    for line in lines:  # проходим по всем строкам
        if line.startswith('P:'):  # если строка начинается с P: (название пакета)
            current_package = line[2:]  # убираем 'P:' и получаем название пакета
            in_target_package = (current_package == package_name)  # проверяем совпадение с искомым пакетом

        elif line.startswith('V:'):  # если строка начинается с V: (версия пакета)
            if in_target_package and package_version and line[2:] != package_version:  # если версия не совпадает
                in_target_package = False  # сбрасываем флаг - версия не совпадает

        elif line.startswith(
                'D:') and in_target_package:  # если строка начинается с D: (зависимости) и мы в целевом пакете
            deps_line = line[2:]  # убираем 'D:' и получаем строку зависимостей
            if deps_line:  # если зависимости есть
                # Разбиваем по пробелам и убираем пустые
                dependencies = [dep.strip() for dep in deps_line.split() if dep.strip()]  # создаем список зависимостей
                break  # Нашли зависимости, выходим из цикла

    return dependencies  # возвращаем список зависимостей


def read_dependencies_from_test_file(package_name, test_repo_path):
    """Читает зависимости из тестового файла (для тестового режима)"""
    try:
        if not os.path.exists(test_repo_path):  # проверяем существование файла
            raise ValueError(f"Тестовый файл не найден: {test_repo_path}")

        with open(test_repo_path, 'r', encoding='utf-8') as f:  # открываем файл для чтения
            content = f.read()  # читаем все содержимое

        # Формат: A: B, C, D (пакет A зависит от B, C, D)
        for line in content.split('\n'):  # разбиваем содержимое на строки
            line = line.strip()  # убираем лишние пробелы
            if line and ':' in line and not line.startswith('#'):  # если строка не пустая и содержит двоеточие и не комментарий
                pkg, deps_str = line.split(':', 1)  # разделяем на пакет и зависимости
                pkg = pkg.strip()  # убираем пробелы у имени пакета
                if pkg == package_name:  # если нашли нужный пакет
                    # Разбиваем зависимости по запятой и убираем пробелы
                    dependencies = [dep.strip() for dep in deps_str.split(',') if dep.strip()]  # создаем список зависимостей
                    return dependencies  # возвращаем зависимости

        return []  # Пакет не найден в тестовом файле

    except Exception as e:  # обработка ошибок
        raise ValueError(f"Ошибка чтения тестового файла: {e}")


def get_package_dependencies(package_name, package_version, repository_url, is_test_mode):
    """
    Универсальная функция для получения зависимостей (режим тестирования или реальный)
    """
    if is_test_mode:  # если тестовый режим
        # Тестовый режим - читаем из файла
        print(f"[ТЕСТОВЫЙ РЕЖИМ] Получаем зависимости для {package_name} из файла")
        return read_dependencies_from_test_file(package_name, repository_url)  # читаем из файла
    else:  # если реальный режим
        # Реальный режим - работаем с Alpine репозиторием
        print(f"[РЕАЛЬНЫЙ РЕЖИМ] Получаем зависимости для {package_name}-{package_version}")
        apkindex_content = download_and_parse_apkindex(repository_url)  # скачиваем и парсим APKINDEX
        return find_package_dependencies(apkindex_content, package_name, package_version)  # ищем зависимости


def build_dependency_graph(package_name, package_version, repository_path, is_test_mode, depth=0, max_depth=10,
                           chain=None):
    """Рекурсивно строит граф зависимостей"""
    if chain is None:  # если цепочка не передана
        chain = []  # создаем пустую цепочку

    if depth > max_depth:  # если превышена максимальная глубина
        print(f"{'  ' * depth}├── {package_name} -> [MAX_DEPTH]")  # выводим сообщение о превышении глубины
        dependency_graph[package_name] = ["MAX_DEPTH_REACHED"]  # добавляем в граф отметку о превышении глубины
        return  # выходим из рекурсии

    # Обнаружение циклических зависимостей
    if package_name in visiting:  # если пакет уже в текущей цепочке (цикл)
        # Правильно показываем цепочку цикла
        current_chain = chain + [package_name]  # добавляем текущий пакет в цепочку
        cycle_start = current_chain.index(package_name)  # находим начало цикла
        cycle_part = current_chain[cycle_start:]  # получаем циклическую часть
        cycle_chain = " → ".join(cycle_part)  # форматируем цикл в строку
        print(f"{'  ' * depth}├── {package_name} ->  ЦИКЛ ({cycle_chain})")  # выводим информацию о цикле
        dependency_graph[package_name] = ["CYCLE: " + cycle_chain]  # добавляем в граф информацию о цикле
        return  # выходим из рекурсии

    if package_name in visited:  # если пакет уже полностью обработан
        return  # выходим из рекурсии

    visiting.add(package_name)  # добавляем пакет в текущую цепочку
    current_chain = chain + [package_name]  # обновляем текущую цепочку

    try:
        # Получаем прямые зависимости
        dependencies = get_package_dependencies(package_name, package_version, repository_path, is_test_mode)  # получаем зависимости пакета

        # Сохраняем в граф
        dependency_graph[package_name] = dependencies  # добавляем зависимости в граф

        # Показываем зависимости
        if dependencies:  # если зависимости есть
            print(f"{'  ' * depth}├── {package_name} -> {dependencies}")  # выводим пакет и его зависимости
        else:
            print(f"{'  ' * depth}├── {package_name} -> []")  # выводим пакет без зависимостей

        # Рекурсивный обход зависимостей
        for dep in dependencies:  # для каждой зависимости
            build_dependency_graph(dep, None, repository_path, is_test_mode, depth + 1, max_depth, current_chain)  # рекурсивно строим граф для зависимости

    except Exception as e:  # обработка ошибок
        print(f"{'  ' * depth}├── {package_name} -> ОШИБКА: {e}")  # выводим информацию об ошибке
        dependency_graph[package_name] = ["ERROR"]  # добавляем в граф отметку об ошибке

    finally:
        visiting.remove(package_name)  # удаляем пакет из текущей цепочки
        visited.add(package_name)  # добавляем пакет в посещенные


def display_parameters(config):
    """Выводит все параметры в формате ключ-значение"""
    print("Параметры конфигурации:")
    for key, value in config.items():  # проходим по всем элементам конфигурации
        print(f"{key}: {value}")  # выводим ключ-значение


def display_dependencies(package_name, dependencies):
    """Выводит прямые зависимости пакета"""
    print(f"\nПрямые зависимости пакета {package_name}:")
    if dependencies:  # если зависимости есть
        for i, dep in enumerate(dependencies, 1):  # нумеруем с 1
            print(f"{i}. {dep}")  # выводим номер и зависимость
    else:
        print("Зависимости не найдены")  # сообщение об отсутствии зависимостей


def display_dependency_graph():
    """Выводит построенный граф зависимостей"""
    print("\n" + "=" * 60)  # разделительная линия
    print("ПОСТРОЕННЫЙ ГРАФ ЗАВИСИМОСТЕЙ")  # заголовок
    print("=" * 60)  # разделительная линия

    for package, dependencies in dependency_graph.items():  # проходим по всем пакетам в графе
        if dependencies:  # если есть зависимости
            deps_str = ", ".join(dependencies)  # объединяем зависимости в строку
            print(f"{package} -> [{deps_str}]")  # выводим пакет и его зависимости
        else:
            print(f"{package} -> []")  # выводим пакет без зависимостей


def create_test_files():
    """Создает тестовые файлы для демонстрации"""
    test_files = {  # словарь тестовых файлов
        "test_simple.txt": """A: B, C
B: D
C: E
D: 
E: F
F:""",  # простой граф

        "test_cycle.txt": """A: B
B: C  
C: A
D: E
E:""",  # граф с циклом

        "test_diamond.txt": """A: B, C
B: D
C: D
D: E
E:""",  # ромбовидный граф

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
L:"""  # сложный граф
    }

    for filename, content in test_files.items():  # проходим по всем тестовым файлам
        if not os.path.exists(filename):  # создаем только если файл не существует
            with open(filename, 'w', encoding='utf-8') as f:  # открываем файл для записи
                f.write(content)  # записываем содержимое
            print(f"Создан тестовый файл: {filename}")  # сообщаем о создании файла


def interactive_test_mode():
    """Интерактивный режим тестирования - пользователь сам все выбирает"""
    print("\n" + "=" * 50)  # разделительная линия
    print("ИНТЕРАКТИВНЫЙ РЕЖИМ ТЕСТИРОВАНИЯ")  # заголовок
    print("=" * 50)  # разделительная линия

    # 1. Пользователь вводит путь к файлу
    while True:  # бесконечный цикл до получения корректного пути
        file_path = input("\n Введите путь к тестовому файлу (например: my_graph.txt): ").strip()  # запрашиваем путь к файлу

        if not file_path:  # если путь пустой
            print(" Путь не может быть пустым!")  # сообщение об ошибке
            continue  # продолжаем цикл

        # Добавляем расширение .txt если его нет
        if not file_path.endswith('.txt'):  # если нет расширения .txt
            file_path += '.txt'  # добавляем расширение

        if os.path.exists(file_path):  # если файл существует
            break  # выходим из цикла
        else:
            print(f" Файл '{file_path}' не найден!")  # сообщение об ошибке
            print(" Создайте файл в формате:")  # подсказка по формату
            print("   A: B, C")  # пример формата
            print("   B: D")  # пример формата
            print("   C: E")  # пример формата
            print("   D:")  # пример формата
            print("   E:")  # пример формата

    # 2. Показываем пакеты из выбранного файла
    print(f"\n Анализируем файл {file_path}...")  # информационное сообщение

    packages = []  # список для хранения пакетов
    try:
        with open(file_path, 'r', encoding='utf-8') as f:  # открываем файл для чтения
            for line in f:  # читаем файл построчно
                line = line.strip()  # убираем пробелы
                if line and ':' in line and not line.startswith('#'):  # если строка не пустая и содержит двоеточие и не комментарий
                    pkg = line.split(':', 1)[0].strip()  # извлекаем имя пакета
                    if pkg and pkg not in packages:  # если пакет не пустой и еще не в списке
                        packages.append(pkg)  # добавляем пакет в список
    except Exception as e:  # обработка ошибок чтения
        print(f" Ошибка чтения файла: {e}")  # выводим ошибку
        return  # выходим из функции

    if not packages:  # если пакеты не найдены
        print(" В файле не найдены пакеты!")  # сообщение об ошибке
        return  # выходим из функции

    print(" Найденные пакеты в файле:")  # заголовок списка пакетов
    for i, pkg in enumerate(packages, 1):  # нумеруем пакеты с 1
        print(f"   {i}. {pkg}")  # выводим номер и имя пакета

    # 3. Пользователь выбирает пакет для анализа
    while True:  # бесконечный цикл до выбора пакета
        try:
            pkg_choice = input(f"\nВыберите пакет для анализа (1-{len(packages)}) или введите свой: ").strip()  # запрашиваем выбор пакета
            if not pkg_choice:  # если выбор пустой
                print(" Введите номер или имя пакета!")  # сообщение об ошибке
                continue  # продолжаем цикл

            if pkg_choice.isdigit():  # если введено число
                pkg_index = int(pkg_choice) - 1  # преобразуем в индекс (начиная с 0)
                if 0 <= pkg_index < len(packages):  # если индекс в допустимом диапазоне
                    selected_package = packages[pkg_index]  # выбираем пакет по индексу
                    break  # выходим из цикла
                else:
                    print(f" Введите число от 1 до {len(packages)}!")  # сообщение об ошибке
            else:
                selected_package = pkg_choice.upper()  # преобразуем в верхний регистр
                break  # выходим из цикла
        except ValueError:  # обработка ошибки преобразования
            print(" Введите корректный номер или имя пакета!")  # сообщение об ошибке

    # 4. Запускаем построение графа
    print(f"\n Запускаем построение графа для пакета '{selected_package}' из файла '{file_path}'...")  # информационное сообщение

    # Очищаем глобальные структуры
    dependency_graph.clear()  # очищаем граф зависимостей
    visited.clear()  # очищаем посещенные пакеты
    visiting.clear()  # очищаем текущую цепочку

    # Строим граф
    build_dependency_graph(  # вызываем построение графа
        selected_package,  # выбранный пакет
        None,  # версия не указана
        file_path,  # передаем путь к файлу, который ввел пользователь
        True  # тестовый режим
    )

    # Показываем результат
    display_dependency_graph()  # выводим построенный граф

    # 5. Предлагаем проанализировать другой пакет
    while True:  # бесконечный цикл для повторного анализа
        another = input("\nПроанализировать другой пакет из этого файла? (y/n): ").strip().lower()  # запрашиваем продолжение
        if another in ['y', 'yes', 'д', 'да']:  # если пользователь хочет продолжить
            # Выбираем новый пакет
            while True:  # бесконечный цикл до выбора пакета
                new_pkg = input(f"Введите имя пакета или номер (1-{len(packages)}): ").strip()  # запрашиваем новый пакет
                if not new_pkg:  # если ввод пустой
                    continue  # продолжаем цикл

                if new_pkg.isdigit():  # если введено число
                    pkg_index = int(new_pkg) - 1  # преобразуем в индекс
                    if 0 <= pkg_index < len(packages):  # если индекс в диапазоне
                        selected_package = packages[pkg_index]  # выбираем пакет по индексу
                        break  # выходим из цикла
                else:
                    selected_package = new_pkg.upper()  # преобразуем в верхний регистр
                    break  # выходим из цикла

            # Очищаем и перестраиваем граф
            dependency_graph.clear()  # очищаем граф
            visited.clear()  # очищаем посещенные
            visiting.clear()  # очищаем текущую цепочку

            print(f"\n Запускаем построение графа для пакета '{selected_package}'...")  # информационное сообщение
            build_dependency_graph(selected_package, None, file_path, True)  # строим граф для нового пакета
            display_dependency_graph()  # выводим граф
        else:
            break  # выходим из цикла


def main():
    """Основная функция приложения"""
    if len(sys.argv) < 2:  # проверяем количество аргументов
        print("Использование:")  # выводим справку
        print("  python main.py <config.xml>    - режим с конфигурационным файлом")  # режим с конфигом
        print("  python main.py --interactive   - интерактивный тестовый режим")  # интерактивный режим
        sys.exit(1)  # выходим с ошибкой

    if sys.argv[1] == "--interactive":  # интерактивный режим
        interactive_test_mode()  # запускаем интерактивный режим
    else:  # режим с конфигурационным файлом
        config_path = sys.argv[1]  # получаем путь к конфигурационному файлу
        try:
            # Этап 1: Загрузка конфигурации
            config = parse_config(config_path)  # парсим конфигурацию
            display_parameters(config)  # выводим параметры

            # Создаем тестовые файлы (для демонстрации)
            create_test_files()  # создаем тестовые файлы

            # Этап 2: Получение прямых зависимостей
            print("\n")  # пустая строка
            dependencies = get_package_dependencies(  # получаем прямые зависимости
                config['package_name'],  # имя пакета из конфига
                config['package_version'],  # версия пакета из конфига
                config['repository_url'],  # URL репозитория из конфига
                config['test_repo_mode']  # режим тестирования из конфига
            )

            display_dependencies(config['package_name'], dependencies)  # выводим прямые зависимости

            # Этап 3: Построение полного графа зависимостей
            print("\n")  # пустая строка
            # Очищаем глобальные структуры перед построением графа
            dependency_graph.clear()  # очищаем граф
            visited.clear()  # очищаем посещенные пакеты
            visiting.clear()  # очищаем текущую цепочку

            build_dependency_graph(  # строим полный граф зависимостей
                config['package_name'],  # имя пакета
                config['package_version'],  # версия пакета
                config['repository_url'],  # URL репозитория
                config['test_repo_mode']  # режим тестирования
            )

            display_dependency_graph()  # выводим построенный граф

        except ValueError as e:  # обработка ожидаемых ошибок
            print(f"Ошибка: {e}")  # выводим ошибку
            sys.exit(1)  # выходим с ошибкой
        except Exception as e:  # обработка неожиданных ошибок
            print(f"Неожиданная ошибка: {e}")  # выводим ошибку
            sys.exit(1)  # выходим с ошибкой


if __name__ == "__main__":
    main()  # запускаем основную функцию