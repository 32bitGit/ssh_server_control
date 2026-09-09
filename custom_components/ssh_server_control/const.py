"""Константы для интеграции SSH Server Control."""

DOMAIN = "ssh_server_control"

# Универсальные дефолтные настройки для автозаполнения форм в GUI
DEFAULT_SERVER_NAME = "Linux Server"
DEFAULT_SERVER_IP = "127.0.0.1"
DEFAULT_SERVER_PORT = 22
DEFAULT_SERVER_USER = "root"
DEFAULT_KEY_PATH = "/config/.ssh/id_rsa"

# Ключи для хранения конфигурации в entry.data и entry.options
CONF_SERVER_NAME = "server_name"
CONF_SERVER_IP = "server_ip"
CONF_SERVER_PORT = "server_port"
CONF_SERVER_USER = "server_user"
CONF_KEY_PATH = "key_path"

CONF_BUTTONS = "buttons"
CONF_SENSORS = "sensors"
