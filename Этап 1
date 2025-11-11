import xml.etree.ElementTree as ET  # Импорт парсера XML
import sys  # Импорт для работы с аргументами командной строки
import os  # Импорт для работы с файловой системой

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

def display_parameters(config):
    """Выводит все параметры в формате ключ-значение"""
    print("Параметры конфигурации:")  # Заголовок
    print("-" * 30)  # Разделитель
    for key, value in config.items():  # Перебор всех параметров
        print(f"{key}: {value}")  # Вывод ключ-значение
    print("-" * 30)  # Разделитель

def main():
    """Основная функция приложения"""
    if len(sys.argv) != 2:  # Проверка количества аргументов
        print("Использование: python main.py <config_file.xml>")  # Сообщение об использовании
        print("Пример: python main.py config.xml")  # Пример использования
        sys.exit(1)  # Выход с ошибкой

    config_file = sys.argv[1]  # Получение пути к конфигурационному файлу

    try:
        config = parse_config(config_file)  # Парсинг конфигурации
        display_parameters(config)  # Вывод параметров
        print("Конфигурация успешно загружена и проверена!")  # Сообщение об успехе

    except ValueError as e:  # Обработка ошибок валидации
        print(f"Ошибка конфигурации: {e}")
        sys.exit(1)  # Выход с ошибкой
    except Exception as e:  # Обработка критических ошибок
        print(f"Критическая ошибка: {e}")
        sys.exit(1)  # Выход с ошибкой

if __name__ == "__main__":
    main()  # Запуск основной функции
