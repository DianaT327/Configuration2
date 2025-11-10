import xml.etree.ElementTree as ET  # для работы с XML файлами
import sys  # для работы с аргументами командной строки
import os   # для проверки существования файлов

def parse_config(config_path):
    """Парсит конфигурационный файл XML и возвращает параметры"""
    try:
        # Проверяем существование файла
        if not os.path.exists(config_path):
            raise ValueError(f"Конфигурационный файл не найден: {config_path}")

        tree = ET.parse(config_path)  # парсим XML файл
        root = tree.getroot()  # получаем корневой элемент

        config = {}  # словарь для хранения параметров

        # Имя анализируемого пакета
        package_name_elem = root.find('package_name')  # ищем элемент package_name
        if package_name_elem is None or not package_name_elem.text:  # если элемент не найден или пустой
            raise ValueError("Отсутствует обязательный параметр: package_name")
        config['package_name'] = package_name_elem.text  # сохраняем значение

        # URL-адрес репозитория или путь к файлу
        repository_url_elem = root.find('repository_url')  # ищем элемент repository_url
        if repository_url_elem is None or not repository_url_elem.text:  # если элемент не найден или пустой
            raise ValueError("Отсутствует обязательный параметр: repository_url")
        config['repository_url'] = repository_url_elem.text  # сохраняем значение

        # Режим работы с тестовым репозиторием
        test_repo_mode_elem = root.find('test_repo_mode')  # ищем элемент test_repo_mode
        if test_repo_mode_elem is not None and test_repo_mode_elem.text:  # если элемент существует и не пустой
            config['test_repo_mode'] = test_repo_mode_elem.text
        else:
            config['test_repo_mode'] = 'local'  # значение по умолчанию

        # Версия пакета
        package_version_elem = root.find('package_version')  # ищем элемент package_version
        if package_version_elem is not None and package_version_elem.text:  # если элемент существует и не пустой
            config['package_version'] = package_version_elem.text  # сохраняем значение
        else:
            config['package_version'] = '1.0.0'  # значение по умолчанию

        # Режим вывода зависимостей в формате ASCII-дерева
        ascii_tree_output_elem = root.find('ascii_tree_output')  # ищем элемент ascii_tree_output
        if ascii_tree_output_elem is not None and ascii_tree_output_elem.text:  # если элемент существует и не пустой
            config['ascii_tree_output'] = ascii_tree_output_elem.text.lower() == 'true'  # преобразуем в булево значение
        else:
            config['ascii_tree_output'] = False  # значение по умолчанию

        return config  # возвращаем словарь с параметрами

    except ET.ParseError as e:  # ошибка парсинга XML
        raise ValueError(f"Ошибка парсинга XML: {e}")
    except Exception as e:  # любые другие ошибки
        raise ValueError(f"Ошибка загрузки конфигурации: {e}")


def display_parameters(config):
    """
    Выводит все параметры в формате ключ-значение
    """
    print("Параметры конфигурации:")  # заголовок
    for key, value in config.items():  # перебираем все пары ключ-значение
        print(f"{key}: {value}")  # выводим каждую пару


def main():
    """Основная функция приложения"""
    if len(sys.argv) != 2:  # проверяем количество аргументов командной строки
        print("Использование: python main.py <config_file.xml>")  # сообщение об использовании
        sys.exit(1)  # завершаем программу с кодом ошибки

    config_file = sys.argv[1]  # получаем имя конфигурационного файла из аргументов

    try:
        config = parse_config(config_file)  # парсим конфигурационный файл
        display_parameters(config)  # выводим параметры

    except ValueError as e:  # обрабатываем ошибки валидации
        print(f"Ошибка: {e}")
        sys.exit(1)  # завершаем с кодом ошибки
    except Exception as e:  # обрабатываем неожиданные ошибки
        print(f"Неожиданная ошибка: {e}")
        sys.exit(1)  # завершаем с кодом ошибки


if __name__ == "__main__":  # если скрипт запущен напрямую
    main()  # запускаем основную функцию