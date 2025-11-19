#!/usr/bin/env python3
import configparser
import argparse
import sys
import os

class CargoRepository:
    def __init__(self, repo_url):
        self.repo_url = repo_url.rstrip('/')
    
    def get_package_dependencies(self, package, version):
        """Получение зависимостей пакета из тестового файла"""
        if self.repo_url.startswith('file://'):
            filepath = self.repo_url[7:]
            return self._parse_test_file(filepath, package, version)
        return []
    
    def _parse_test_file(self, filepath, package, version):
        """Парсинг тестового файла с зависимостями"""
        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                for line in f:
                    line = line.strip()
                    if line and '->' in line:
                        parts = line.split('->')
                        pkg_info = parts[0].strip()
                        
                        # Разделяем имя пакета и версию
                        if '@' in pkg_info:
                            pkg_name, pkg_ver = pkg_info.split('@')
                        else:
                            pkg_name, pkg_ver = pkg_info, ''
                        
                        # Проверяем соответствие пакета и версии
                        if pkg_name == package and (not version or pkg_ver == version):
                            deps = [p.strip() for p in parts[1].split(',')]
                            # Убираем версии для чистоты вывода
                            clean_deps = [d.split('@')[0] for d in deps if d.strip()]
                            return clean_deps
        except FileNotFoundError:
            print(f"Ошибка: файл {filepath} не найден")
        except Exception as e:
            print(f"Ошибка чтения файла: {e}")
        
        return []

def run_stage1(config_path):
    """Выполнение этапа 1"""
    print("=== ЭТАП 1: МИНИМАЛЬНЫЙ ПРОТОТИП С КОНФИГУРАЦИЕЙ ===")
    
    # 1. Чтение INI конфигурации
    if not os.path.exists(config_path):
        print(f"Ошибка: файл {config_path} не найден")
        return 1
    
    config = configparser.ConfigParser()
    try:
        config.read(config_path)
    except Exception as e:
        print(f"Ошибка чтения конфигурации: {e}")
        return 1
    
    if 'DEFAULT' not in config:
        print("Ошибка: не найден раздел [DEFAULT]")
        return 1
    
    config_dict = dict(config['DEFAULT'])
    
    # 2. Извлечение параметров
    package_name = config_dict.get('package_name', '')
    repository_url = config_dict.get('repository_url', '')
    package_version = config_dict.get('package_version', '')
    max_depth = config_dict.get('max_depth', '')
    exclude_substring = config_dict.get('exclude_substring', '')
    
    # 3. Валидация параметров
    errors = []
    if not package_name:
        errors.append("Не указано имя пакета")
    if not repository_url:
        errors.append("Не указан URL репозитория")
    
    if errors:
        print("Ошибки конфигурации:")
        for error in errors:
            print(f"  - {error}")
        return 1
    
    # 4. Вывод параметров (требование этапа)
    print("Параметры конфигурации:")
    print(f"  package_name: {package_name}")
    print(f"  repository_url: {repository_url}")
    print(f"  package_version: {package_version}")
    print(f"  max_depth: {max_depth}")
    print(f"  exclude_substring: {exclude_substring}")
    
    # 5. Обработка ошибок параметров
    try:
        if max_depth:
            depth = int(max_depth)
            if depth <= 0:
                print("Ошибка: max_depth должен быть положительным числом")
                return 1
    except ValueError:
        print("Ошибка: max_depth должен быть числом")
        return 1
    
    print("Конфигурация загружена успешно")
    return 0

def run_stage2(config_path):
    """Выполнение этапа 2"""
    print("=== ЭТАП 2: СБОР ДАННЫХ ===")
    
    # 1. Чтение конфигурации
    if not os.path.exists(config_path):
        print(f"Ошибка: файл {config_path} не найден")
        return 1
    
    config = configparser.ConfigParser()
    try:
        config.read(config_path)
    except Exception as e:
        print(f"Ошибка чтения конфигурации: {e}")
        return 1
    
    if 'DEFAULT' not in config:
        print("Ошибка: не найден раздел [DEFAULT]")
        return 1
    
    config_dict = dict(config['DEFAULT'])
    
    # 2. Извлечение параметров
    package = config_dict.get('package_name', 'serde')
    repo_url = config_dict.get('repository_url', 'file://test_repo.txt')
    version = config_dict.get('package_version', '1.0')
    
    print(f"Поиск зависимостей для {package} версии {version}")
    
    # 3. Получение зависимостей
    repo = CargoRepository(repo_url)
    deps = repo.get_package_dependencies(package, version)
    
    # 4. Вывод прямых зависимостей (требование этапа)
    print(f"Прямые зависимости пакета {package}:")
    if deps:
        for dep in deps:
            print(f"  - {dep}")
    else:
        print("  Зависимости не найдены")
    
    return 0

def main():
    parser = argparse.ArgumentParser(description='Визуализатор графа зависимостей')
    parser.add_argument('--config', required=True, help='Путь к INI-файлу конфигурации')
    parser.add_argument('--stage', type=int, default=1, help='Номер этапа для выполнения (1-5)')
    args = parser.parse_args()
    
    if args.stage == 1:
        return run_stage1(args.config)
    elif args.stage == 2:
        return run_stage2(args.config)
    else:
        print(f"Этап {args.stage} еще не реализован")
        return 1

if __name__ == "__main__":
    sys.exit(main())