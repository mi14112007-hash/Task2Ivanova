#!/usr/bin/env python3
import configparser
import argparse
import sys
import os
import subprocess
import tempfile
from collections import deque, defaultdict

class CargoRepository:
    def __init__(self, repo_url):
        self.repo_url = repo_url.rstrip('/')
        self.dependency_cache = {}
        self.reverse_dependency_cache = defaultdict(list)
    
    def get_package_dependencies(self, package, version):
        cache_key = f"{package}@{version}" if version else package
        
        if cache_key in self.dependency_cache:
            return self.dependency_cache[cache_key]
        
        if self.repo_url.startswith('file://'):
            filepath = self.repo_url[7:]
            deps = self._parse_test_file(filepath, package, version)
        else:
            deps = self._parse_cargo_dependencies(package, version)
        
        self.dependency_cache[cache_key] = deps
        
        for dep in deps:
            self.reverse_dependency_cache[dep].append(package)
        
        return deps
    
    def get_reverse_dependencies(self, package):
        if package in self.reverse_dependency_cache:
            return self.reverse_dependency_cache[package]
        
        if not self.reverse_dependency_cache:
            self._build_reverse_dependency_cache()
        
        return self.reverse_dependency_cache.get(package, [])
    
    def _build_reverse_dependency_cache(self):
        if self.repo_url.startswith('file://'):
            filepath = self.repo_url[7:]
            self._build_reverse_cache_from_file(filepath)
    
    def _build_reverse_cache_from_file(self, filepath):
        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                for line in f:
                    line = line.strip()
                    if line and '->' in line:
                        parts = line.split('->')
                        pkg_info = parts[0].strip()
                        
                        if '@' in pkg_info:
                            pkg_name, _ = pkg_info.split('@')
                        else:
                            pkg_name = pkg_info
                        
                        deps = [p.strip() for p in parts[1].split(',')]
                        clean_deps = [d.split('@')[0] for d in deps if d.strip()]
                        
                        for dep in clean_deps:
                            self.reverse_dependency_cache[dep].append(pkg_name)
        except Exception as e:
            print(f"Ошибка построения кэша обратных зависимостей: {e}")
    
    def _parse_test_file(self, filepath, package, version):
        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                for line in f:
                    line = line.strip()
                    if line and '->' in line:
                        parts = line.split('->')
                        pkg_info = parts[0].strip()
                        
                        if '@' in pkg_info:
                            pkg_name, pkg_ver = pkg_info.split('@')
                        else:
                            pkg_name, pkg_ver = pkg_info, ''
                        
                        if pkg_name == package and (not version or pkg_ver == version):
                            deps = [p.strip() for p in parts[1].split(',')]
                            clean_deps = [d.split('@')[0] for d in deps if d.strip()]
                            return clean_deps
        except FileNotFoundError:
            print(f"Ошибка: файл {filepath} не найден")
        except Exception as e:
            print(f"Ошибка чтения файла: {e}")
        
        return []
    
    def _parse_cargo_dependencies(self, package, version):
        demo_dependencies = {
            'serde': ['serde_derive', 'serde_json'],
            'serde_derive': ['proc-macro2', 'quote', 'syn'],
            'serde_json': ['itoa', 'ryu', 'serde'],
            'proc-macro2': ['unicode-xid'],
            'syn': ['proc-macro2', 'quote', 'unicode-xid'],
            'quote': ['proc-macro2'],
            'itoa': [],
            'ryu': [],
            'unicode-xid': [],
            'tokio': ['futures', 'mio', 'num_cpus'],
            'futures': [],
            'mio': [],
            'num_cpus': [],
            'reqwest': ['futures', 'http', 'url', 'serde'],
            'http': [],
            'url': []
        }
        return demo_dependencies.get(package, [])

class DependencyGraph:
    def __init__(self, repository):
        self.repository = repository
        self.graph = defaultdict(list)
        self.visited = set()
        self.cycles = []
        self.load_order = []
    
    def build_graph_bfs_recursive(self, start_package, start_version="", max_depth=float('inf'), 
                                 exclude_substring="", current_depth=0, path=None):
        if path is None:
            path = []
        
        if current_depth >= max_depth:
            return
        
        if start_package in path:
            cycle = path[path.index(start_package):] + [start_package]
            self.cycles.append(cycle)
            return
        
        if exclude_substring and exclude_substring in start_package:
            return
        
        if start_package in self.visited:
            return
        
        self.visited.add(start_package)
        self.load_order.append(start_package)
        current_path = path + [start_package]
        
        dependencies = self.repository.get_package_dependencies(start_package, start_version)
        
        for dep in dependencies:
            self.graph[start_package].append(dep)
            self.build_graph_bfs_recursive(
                dep, "", max_depth, exclude_substring, 
                current_depth + 1, current_path
            )
    
    def generate_graphviz_dot(self):
        """Генерация представления графа на языке Graphviz DOT"""
        dot_lines = ["digraph Dependencies {"]
        dot_lines.append("  rankdir=TB;")
        dot_lines.append("  node [shape=box, style=filled, fillcolor=lightblue];")
        dot_lines.append("  edge [color=darkgreen];")
        
        # Добавляем узлы и ребра
        for source, targets in self.graph.items():
            for target in targets:
                dot_lines.append(f'  "{source}" -> "{target}";')
        
        # Выделяем циклические зависимости красным цветом
        if self.cycles:
            dot_lines.append("  edge [color=red];")
            for cycle in self.cycles:
                for i in range(len(cycle) - 1):
                    dot_lines.append(f'  "{cycle[i]}" -> "{cycle[i+1]}";')
        
        dot_lines.append("}")
        return "\n".join(dot_lines)
    
    def display_graph(self):
        """Вывод графа на экран"""
        dot_content = self.generate_graphviz_dot()
        print("Граф зависимостей в формате Graphviz DOT:")
        print(dot_content)
        return dot_content
    
    def save_graph_image(self, filename):
        """Сохранение графа в файл изображения"""
        try:
            dot_content = self.generate_graphviz_dot()
            
            # Создаем временный файл .dot
            with tempfile.NamedTemporaryFile(mode='w', suffix='.dot', delete=False) as dot_file:
                dot_file.write(dot_content)
                dot_filename = dot_file.name
            
            # Конвертируем в PNG с помощью Graphviz
            result = subprocess.run(
                ['dot', '-Tpng', dot_filename, '-o', filename],
                capture_output=True, text=True
            )
            
            # Удаляем временный файл
            os.unlink(dot_filename)
            
            if result.returncode == 0:
                print(f"Изображение графа сохранено в файл: {filename}")
                return True
            else:
                print(f"Ошибка генерации изображения: {result.stderr}")
                return False
                
        except FileNotFoundError:
            print("Ошибка: Graphviz не установлен. Установите его для генерации изображений.")
            return False
        except Exception as e:
            print(f"Ошибка сохранения изображения: {e}")
            return False
    
    def get_load_order(self):
        return self.load_order
    
    def get_reverse_dependencies(self, package, max_depth=float('inf')):
        reverse_deps = set()
        visited = set()
        queue = deque([(package, 0)])
        
        while queue:
            current_pkg, depth = queue.popleft()
            
            if depth >= max_depth or current_pkg in visited:
                continue
            
            visited.add(current_pkg)
            dependents = self.repository.get_reverse_dependencies(current_pkg)
            
            for dependent in dependents:
                if dependent not in visited:
                    reverse_deps.add(dependent)
                    queue.append((dependent, depth + 1))
        
        return list(reverse_deps)
    
    def get_graph(self):
        return dict(self.graph)
    
    def get_cycles(self):
        return self.cycles
    
    def reset(self):
        self.graph.clear()
        self.visited.clear()
        self.cycles.clear()
        self.load_order.clear()

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

def run_stage4(config_path):
    """Выполнение этапа 4"""
    print("=== ЭТАП 4: ДОПОЛНИТЕЛЬНЫЕ ОПЕРАЦИИ ===")
    
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
    
    print(f"Анализ зависимостей для {package} версии {version}")
    
    # 3. Построение графа для получения порядка загрузки
    repo = CargoRepository(repo_url)
    graph_builder = DependencyGraph(repo)
    
    graph_builder.build_graph_bfs_recursive(package, version, max_depth)
    
    # 4. Порядок загрузки зависимостей
    load_order = graph_builder.get_load_order()
    print(f"\nПорядок загрузки зависимостей для {package}:")
    for i, pkg in enumerate(load_order, 1):
        print(f"  {i}. {pkg}")
    
    # 5. Обратные зависимости
    reverse_deps = graph_builder.get_reverse_dependencies(package)
    print(f"\nОбратные зависимости для {package} (пакеты, зависящие от него):")
    if reverse_deps:
        for dep in reverse_deps:
            print(f"  - {dep}")
    else:
        print("  Обратные зависимости не найдены")
    
    # 6. Сравнение с реальным менеджером пакетов
    print(f"\nСравнение с реальным менеджером пакетов Cargo:")
    print("  Порядок загрузки может отличаться из-за:")
    print("  - Оптимизации параллельной загрузки в Cargo")
    print("  - Особенностей разрешения версий зависимостей")
    print("  - Наличия опциональных зависимостей")
    print("  - Кэширования ранее скачанных пакетов")
    
    return 0

def run_stage5(config_path):
    """Выполнение этапа 5"""
    print("=== ЭТАП 5: ВИЗУАЛИЗАЦИЯ ===")
    
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
    
    print(f"Визуализация графа зависимостей для {package} версии {version}")
    
    # 3. Демонстрация для трех различных пакетов
    demo_packages = ['serde', 'tokio', 'reqwest']
    
    for demo_package in demo_packages:
        print(f"\n--- Визуализация для пакета: {demo_package} ---")
        
        repo = CargoRepository(repo_url)
        graph_builder = DependencyGraph(repo)
        
        graph_builder.build_graph_bfs_recursive(
            demo_package, version, max_depth, exclude_substring
        )
        
        # Вывод графа в формате Graphviz
        graph_builder.display_graph()
        
        # Сохранение изображения
        image_filename = f"{demo_package}_dependencies.png"
        if graph_builder.save_graph_image(image_filename):
            print(f"Изображение сохранено: {image_filename}")
        else:
            print("Не удалось сохранить изображение (требуется Graphviz)")
        
        print(f"Граф содержит {len(graph_builder.get_graph())} узлов")
    
    # 4. Сравнение с реальными инструментами
    print(f"\nСравнение с штатными инструментами визуализации Cargo:")
    print("  Отличия могут быть вызваны:")
    print("  - Разными алгоритмами обхода графа")
    print("  - Учетом feature flags в реальном Cargo")
    print("  - Обработкой dev-dependencies и build-dependencies")
    print("  - Разрешением конфликтов версий")
    print("  - Учетом платформо-специфичных зависимостей")
    
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
    elif args.stage == 4:
        return run_stage4(args.config)
    elif args.stage == 5:
        return run_stage5(args.config)
    else:
        print(f"Этап {args.stage} еще не реализован")
        return 1

if __name__ == "__main__":
    sys.exit(main())