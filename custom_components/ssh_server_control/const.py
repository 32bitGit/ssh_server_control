"""Глобальные внешние параметры, дефолты и ссылки интеграции SSH Server Control."""

DOMAIN = "ssh_server_control"

# ТЗ: Оставляем здесь ИСКЛЮЧИТЕЛЬНО внешние адреса, пути и дефолты, написанные через пробелы
URL_GITHUB_API = "https://api.github.com/repos/immich-app/immich/releases/latest"
PREFIX_HTTP = "http://"
PREFIX_HTTPS = "https://"

# Дефолтные параметры Универсального сервера
DEFAULT_SERVER_NAME = "Linux Server"
DEFAULT_IMMICH_SERVER_NAME = "Immich Server"
DEFAULT_SERVER_IP = "127.0.0.1"
DEFAULT_SERVER_PORT = 22
DEFAULT_SERVER_USER = "bit"
DEFAULT_KEY_PATH = "/config/.ssh/id_rsa"
DEFAULT_SERVER_PASSWORD = ""

# Дефолтные пути и параметры контейнеров Immich для удобной очистки в одном месте
DEFAULT_IMMICH_COMPOSE_PATH = "/home/bit/immich-app/docker-compose.yml"
DEFAULT_IMMICH_BACKUP_PATH = "/mnt/hdd/immich-backups"
DEFAULT_IMMICH_DB_USER = "32bit"

# 1. Шаблон состояния по умолчанию для сенсора Immich Update (Определяем ПЕРВЫМ)
DEFAULT_IMMICH_UPDATE_VALUE_TEMPLATE = (
    "{{ display_version if update_available else value }}"
)


# 1. Защищенный шаблон доступности кнопки, игнорирующий выполнение, если ID еще равны None
DEFAULT_IMMICH_UPDATE_AVAIL_TEMPLATE = (
    "{% set st = state_attr(up_entity_id, 'status_entity_id') %}"
    "{% set sw = state_attr(up_entity_id, 'force_mode_entity_id') %}"
    "{% if st and sw and states(up_entity_id) not in ['unknown', 'unavailable'] %}"
        "{% if state_attr(up_entity_id, 'breaking_changes') | default(false) == true %}"
        "{{ state_attr(st, 'container_is_running') | default(false) == true and "
        "state_attr(st, 'api_is_online') | default(false) == true and "
        "state_attr(up_entity_id, 'update_available') | default(false) == true and is_state(sw, 'on') }}"
        "{% else %}"
        "{{ state_attr(st, 'container_is_running') | default(false) == true and "
        "state_attr(st, 'api_is_online') | default(false) == true and "
        "state_attr(up_entity_id, 'update_available') | default(false) == true }}"
        "{% endif %}"
    "{% else %}"
    "false"
    "{% endif %}"
)

# 2. Защищенный шаблон доступности тумблера Force Mode
DEFAULT_IMMICH_FORCE_AVAIL_TEMPLATE = (
    "{% if status_entity_id and states(up_entity_id) not in ['unknown', 'unavailable'] %}"
    "{{ state_attr(status_entity_id, 'container_is_running') | default(false) == true and "
    "state_attr(status_entity_id, 'api_is_online') | default(false) == true and "
    "state_attr(up_entity_id, 'breaking_changes') | default(false) == true }}"
    "{% else %}"
    "false"
    "{% endif %}"
)


# Системные дефолтные конфигурации встроенных датчиков Immich
DEFAULT_IMMICH_SENSORS_CONF = {
    "immich_status": {
        "name": "Immich Status",
        "command": "__api_immich_status__",
        "value_template": "",
        "scan_interval": 300,
        "category": "main"
    },
    "immich_update": {
        "name": "Immich Update",
        "command": "__api_immich_update__",
        "value_template": DEFAULT_IMMICH_UPDATE_VALUE_TEMPLATE,
        "scan_interval": 86400,
        "category": "main"
    },
    # ТЗ: Убираем макрос-команду и обнуляем интервал. Датчик переходит на 100% реактивную Jinja-основу
    "immich_last_check": {
        "name": "Immich Last Check",
        "command": "", 
        "value_template": "{{ state_attr(up_entity_id, 'last_check_time') }}",
        "scan_interval": 0,
        "category": "diagnostic"
    }
}

# Системные дефолтные конфигурации встроенных кнопок Immich
DEFAULT_IMMICH_BUTTONS_CONF = {
    "immich_check_update": {
        "name": "Immich Check Update",
        "command": "__api_immich_force_check_update__",
        "wait_for_result": False,
        "category": "main"
    },
    "immich_run_update": {
        "name": "Immich Run Update",
        "command": "__api_immich_run_update_sequence__",
        "wait_for_result": False,
        "availability_template": DEFAULT_IMMICH_UPDATE_AVAIL_TEMPLATE,
        "category": "diagnostic"
    }
}