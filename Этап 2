import xml.etree.ElementTree as ET  # Импорт XML парсера
import sys  # Импорт системных функций
import os  # Импорт работы с ОС
import urllib.request  # Импорт HTTP-запросов
import urllib.error  # Импорт ошибок HTTP
import gzip  # Импорт работы с gzip
import tarfile  # Импорт работы с tar-архивами
from io import BytesIO  # Импорт работы с бинарными данными

def parse_config(config_path):
    """Парсит конфигурационный файл XML и возвращает параметры"""
    try:
        if not os.path.exists(config_path):  # Проверка существования файла
            raise FileNotFoundError(f"Конфигурационный файл не найден: {config_path}")

        if not os.path.isfile(config_path):  # Проверка что это файл
            raise ValueError(f"Указанный путь не является файлом: {config_path}")

        if not config_path.lower().endswith('.xml'):  # Проверка расширения .xml
            raise ValueError(f"Файл должен иметь расширение .xml: {config_path}")

        tree = ET.parse(config_path)  # Парсинг XML файла
        root = tree.getroot()  # Получение корневого элемента

        config = {}  # Словарь для хранения параметров

        package_name_elem = root.find('package_name')  # Поиск элемента package_name
        if package_name_elem is None:  # Проверка наличия элемента
            raise ValueError("Отсутствует обязательный элемент: package_name")

        if package_name_elem.text is None:  # Проверка что элемент не пустой
            raise ValueError("Элемент package_name не может быть пустым")

        package_name = package_name_elem.text.strip()  # Удаление пробелов
        if not package_name:  # Проверка на пустую строку
            raise ValueError("Имя пакета не может быть пустой строкой")

        if not all(c.isalnum() or c in ['-', '_', '.'] for c in package_name):  # Валидация символов
            raise ValueError(f"Недопустимые символы в имени пакета: {package_name}")

        config['package_name'] = package_name  # Сохранение в конфиг

        repository_url_elem = root.find('repository_url')  # Поиск элемента repository_url
        if repository_url_elem is None:  # Проверка наличия элемента
            raise ValueError("Отсутствует обязательный элемент: repository_url")

        if repository_url_elem.text is None:  # Проверка что элемент не пустой
            raise ValueError("Элемент repository_url не может быть пустым")

        repository_url = repository_url_elem.text.strip()  # Удаление пробелов
        if not repository_url:  # Проверка на пустую строку
            raise ValueError("URL репозитория не может быть пустой строкой")

        if repository_url.startswith(('http://', 'https://')):  # Проверка для URL
            if len(repository_url) < 10:  # Минимальная длина URL
                raise ValueError(f"Некорректный URL репозитория: {repository_url}")
        else:  # Проверка для локального пути
            if len(repository_url) < 1:  # Минимальная длина пути
                raise ValueError(f"Некорректный путь к репозиторию: {repository_url}")

        config['repository_url'] = repository_url  # Сохранение в конфиг

        test_repo_mode_elem = root.find('test_repo_mode')  # Поиск элемента test_repo_mode
        if test_repo_mode_elem is not None and test_repo_mode_elem.text:  # Если элемент существует
            test_repo_mode = test_repo_mode_elem.text.strip().lower()  # Приведение к нижнему регистру
            valid_modes = ['local', 'remote', 'docker', 'virtual']  # Допустимые значения
            if test_repo_mode not in valid_modes:  # Проверка допустимости значения
                raise ValueError(f"Недопустимый режим работы: {test_repo_mode}. Допустимые значения: {', '.join(valid_modes)}")
            config['test_repo_mode'] = test_repo_mode  # Сохранение значения
        else:
            config['test_repo_mode'] = 'local'  # Значение по умолчанию

        package_version_elem = root.find('package_version')  # Поиск элемента package_version
        if package_version_elem is not None and package_version_elem.text:  # Если элемент существует
            package_version = package_version_elem.text.strip()  # Удаление пробелов
            if not package_version:  # Проверка на пустую строку
                raise ValueError("Версия пакета не может быть пустой строкой")

            if not any(c.isdigit() for c in package_version):  # Проверка наличия цифр
                raise ValueError(f"Некорректный формат версии пакета: {package_version}")

            config['package_version'] = package_version  # Сохранение значения
        else:
            config['package_version'] = '1.0.0'  # Значение по умолчанию

        ascii_tree_output_elem = root.find('ascii_tree_output')  # Поиск элемента ascii_tree_output
        if ascii_tree_output_elem is not None and ascii_tree_output_elem.text:  # Если элемент существует
            ascii_text = ascii_tree_output_elem.text.strip().lower()  # Приведение к нижнему регистру
            valid_boolean_values = ['true', 'false', '1', '0', 'yes', 'no']  # Допустимые булевы значения

            if ascii_text not in valid_boolean_values:  # Проверка допустимости значения
                raise ValueError(f"Недопустимое значение для ascii_tree_output: {ascii_tree_output_elem.text}. Допустимые значения: true, false")

            config['ascii_tree_output'] = ascii_text in ['true', '1', 'yes']  # Преобразование в bool
        else:
            config['ascii_tree_output'] = False  # Значение по умолчанию

        return config  # Возврат словаря с параметрами

    except ET.ParseError as e:  # Обработка ошибок парсинга XML
        raise ValueError(f"Ошибка парсинга XML: {e}")
    except FileNotFoundError as e:  # Обработка ошибок файла
        raise ValueError(f"Файл не найден: {e}")
    except PermissionError as e:  # Обработка ошибок прав доступа
        raise ValueError(f"Отсутствуют права доступа к файлу: {e}")
    except Exception as e:  # Обработка прочих ошибок
        raise ValueError(f"Неожиданная ошибка при загрузке конфигурации: {e}")

def download_and_parse_apkindex(repository_url):
    """Скачивает и парсит APKINDEX.tar.gz"""
    try:
        # 1. Формируем URL
        if repository_url.endswith('/'):
            apkindex_url = repository_url + 'APKINDEX.tar.gz'
        else:
            apkindex_url = repository_url + '/APKINDEX.tar.gz'

        print(f"Скачиваем {apkindex_url}...")

        # 2. Качаем файл
        with urllib.request.urlopen(apkindex_url) as response:
            apkindex_data = response.read()

        print("Файл скачан, распаковываем...")

        # 3. Распаковываем .tar.gz
        with gzip.GzipFile(fileobj=BytesIO(apkindex_data)) as gz_file:
            tar_data = gz_file.read()

        # 4. Читаем tar архив
        with tarfile.open(fileobj=BytesIO(tar_data)) as tar:
            # В tar архиве один файл - APKINDEX
            apkindex_file = tar.extractfile('APKINDEX')
            apkindex_content = apkindex_file.read().decode('utf-8')

        return apkindex_content

    except Exception as e:
        raise ValueError(f"Ошибка при загрузке APKINDEX: {e}")

def find_package_dependencies(apkindex_content, package_name, package_version):
    """Ищет зависимости пакета в APKINDEX"""
    lines = apkindex_content.split('\n')

    current_package = None
    in_target_package = False
    package_exists = False  # Флаг существования пакета
    dependencies = []

    for line in lines:
        if line.startswith('P:'):  # Название пакета
            current_package = line[2:]
            if current_package == package_name:
                package_exists = True  # Пакет найден!
                in_target_package = True
            else:
                in_target_package = False

        elif line.startswith('V:'):  # Версия пакета
            if in_target_package and package_version and line[2:] != package_version:
                in_target_package = False  # Версия не совпадает

        elif line.startswith('D:') and in_target_package:  # Зависимости
            deps_line = line[2:]
            if deps_line:
                dependencies = [dep.strip() for dep in deps_line.split() if dep.strip()]
            break

    # Возвращаем и зависимости и флаг существования
    return dependencies, package_exists


def get_alpine_dependencies(package_name, package_version, repository_url):
    """
    Получает прямые зависимости пакета Alpine Linux
    """
    try:
        print(f"Получаем зависимости для пакета: {package_name}-{package_version}")
        print(f"Из репозитория: {repository_url}")

        # 1. Скачиваем и парсим APKINDEX
        apkindex_content = download_and_parse_apkindex(repository_url)

        # 2. Ищем зависимости нашего пакета
        dependencies, package_exists = find_package_dependencies(apkindex_content, package_name, package_version)

        if not package_exists:
            raise ValueError(f"Пакет {package_name} не найден в репозитории")

        if not dependencies:
            print(f"Пакет {package_name} не имеет зависимостей")

        return dependencies

    except urllib.error.URLError as e:
        raise ValueError(f"Ошибка при обращении к репозиторию: {e}")
    except Exception as e:
        raise ValueError(f"Ошибка при получении зависимостей: {e}")

def display_dependencies(package_name, dependencies):
    """Выводит прямые зависимости пакета"""
    print(f"\nПрямые зависимости пакета {package_name}:")
    if dependencies:
        for i, dep in enumerate(dependencies, 1):
            print(f"{i}. {dep}")
    else:
        print("Зависимости не найдены")

def main():
    """Основная функция приложения"""
    if len(sys.argv) != 2:
        print("Использование: python main.py <config.xml>")
        sys.exit(1)

    config_path = sys.argv[1]

    try:
        # Этап 1: Загрузка конфигурации
        config = parse_config(config_path)


        # Этап 2: Получение зависимостей
        dependencies = get_alpine_dependencies(
            config['package_name'],
            config['package_version'],
            config['repository_url']
        )

        display_dependencies(config['package_name'], dependencies)

    except ValueError as e:
        print(f"Ошибка: {e}")
        sys.exit(1)
    except Exception as e:
        print(f"Неожиданная ошибка: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
