#!/usr/bin/env python3
import configparser
import argparse
import sys
import os
from collections import deque, defaultdict

class CargoRepository:
    def __init__(self, repo_url):
        self.repo_url = repo_url.rstrip('/')
        self.dependency_cache = {}  # Кэш зависимостей
    
    def get_package_dependencies(self, package, version):
        """Получение зависимостей пакета из тестового файла"""
        cache_key = f"{package}@{version}" if version else package
        
        if cache_key in self.dependency_cache:
            return self.dependency_cache[cache_key]
        
        if self.repo_url.startswith('file://'):
            filepath = self.repo_url[7:]
            deps = self._parse_test_file(filepath, package, version)
        else:
            deps = self._parse_cargo_dependencies(package, version)
        
        self.dependency_cache[cache_key] = deps
        return deps
    
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
    
    def _parse_cargo_dependencies(self, package, version):
        """Заглушка для реального Cargo репозитория"""
        demo_dependencies = {
            'serde': ['serde_derive', 'serde_json'],
            'serde_derive': ['proc-macro2', 'quote', 'syn'],
            'serde_json': ['itoa', 'ryu', 'serde'],
            'proc-macro2': ['unicode-xid'],
            'syn': ['proc-macro2', 'quote', 'unicode-xid'],
            'quote': ['proc-macro2'],
            'itoa': [],
            'ryu': [],
            'unicode-xid': []
        }
        return demo_dependencies.get(package, [])

class DependencyGraph:
    """Класс для работы с графом зависимостей"""
    
    def __init__(self, repository):
        self.repository = repository
        self.graph = defaultdict(list)
        self.visited = set()
        self.cycles = []
    
    def build_graph_bfs_recursive(self, start_package, start_version="", max_depth=float('inf'), 
                                 exclude_substring="", current_depth=0, path=None):
        """Построение графа зависимостей с помощью BFS с рекурсией"""
        if path is None:
            path = []
        
        # Проверка максимальной глубины
        if current_depth >= max_depth:
            return
        
        # Проверка циклических зависимостей
        if start_package in path:
            cycle = path[path.index(start_package):] + [start_package]
            self.cycles.append(cycle)
            return
        
        # Пропускаем пакеты с исключаемой подстрокой
        if exclude_substring and exclude_substring in start_package:
            return
        
        if start_package in self.visited:
            return
        
        self.visited.add(start_package)
        current_path = path + [start_package]
        
        # Получаем зависимости
        dependencies = self.repository.get_package_dependencies(start_package, start_version)
        
        for dep in dependencies:
            self.graph[start_package].append(dep)
            # Рекурсивный вызов для зависимостей
            self.build_graph_bfs_recursive(
                dep, "", max_depth, exclude_substring, 
                current_depth + 1, current_path
            )
    
    def get_graph(self):
        """Получение построенного графа"""
        return dict(self.graph)
    
    def get_cycles(self):
        """Получение найденных циклических зависимостей"""
        return self.cycles
    
    def reset(self):
        """Сброс состояния графа"""
        self.graph.clear()
        self.visited.clear()
        self.cycles.clear()

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

def run_stage3(config_path):
    """Выполнение этапа 3"""
    print("=== ЭТАП 3: ОСНОВНЫЕ ОПЕРАЦИИ ===")
    
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
    max_depth = int(config_dict.get('max_depth', 0)) or float('inf')
    exclude_substring = config_dict.get('exclude_substring', '')
    
    print(f"Построение графа зависимостей для {package} версии {version}")
    print(f"Максимальная глубина: {max_depth if max_depth != float('inf') else 'не ограничена'}")
    if exclude_substring:
        print(f"Исключаемая подстрока: '{exclude_substring}'")
    
    # 3. Построение графа
    repo = CargoRepository(repo_url)
    graph_builder = DependencyGraph(repo)
    
    graph_builder.build_graph_bfs_recursive(
        package, version, max_depth, exclude_substring
    )
    
    # 4. Вывод результатов
    graph = graph_builder.get_graph()
    cycles = graph_builder.get_cycles()
    
    print("\nПостроенный граф зависимостей:")
    for pkg, deps in graph.items():
        print(f"  {pkg} -> {', '.join(deps)}")
    
    if cycles:
        print(f"\nОбнаружены циклические зависимости ({len(cycles)}):")
        for i, cycle in enumerate(cycles, 1):
            print(f"  Цикл {i}: {' -> '.join(cycle)}")
    else:
        print("\nЦиклические зависимости не обнаружены")
    
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
    elif args.stage == 3:
        return run_stage3(args.config)
    else:
        print(f"Этап {args.stage} еще не реализован")
        return 1

if __name__ == "__main__":
    sys.exit(main())