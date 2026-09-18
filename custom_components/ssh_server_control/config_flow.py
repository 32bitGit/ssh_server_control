import logging
import voluptuous as vol
from homeassistant import config_entries
from homeassistant.core import callback
from homeassistant.data_entry_flow import FlowResult

from .const import (
    DOMAIN,
    PREFIX_HTTP,
    PREFIX_HTTPS,
    DEFAULT_SERVER_NAME,
    DEFAULT_IMMICH_SERVER_NAME,
    DEFAULT_SERVER_IP,
    DEFAULT_SERVER_PORT,
    DEFAULT_SERVER_USER,
    DEFAULT_KEY_PATH,
    DEFAULT_IMMICH_COMPOSE_PATH,
    DEFAULT_IMMICH_BACKUP_PATH,
    DEFAULT_IMMICH_DB_USER
)
from .options_flow import SSHServerControlOptionsFlowHandler

_LOGGER = logging.getLogger(__name__)

class SSHServerControlConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Логика первоначальной настройки и конфигурации хаба в интерфейсе."""

    VERSION = 1

    def __init__(self) -> None:
        """Инициализация потока конфигурации."""
        self._hub_type = None
        self._generic_data = {}

    async def async_step_user(self, user_input=None) -> FlowResult:
        """Шаг 1: Выбор типа хаба (Универсальный или Immich)."""
        errors = {}
        if user_input is not None:
            self._hub_type = user_input.get("hub_type", "generic")
            if self._hub_type == "immich":
                return await self.async_step_immich()
            return await self.async_step_generic()

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema({
                vol.Required("hub_type", default="generic"): vol.In([
                    "generic",
                    "immich"
                ])
            }),
            errors=errors
        )

    async def async_step_generic(self, user_input=None) -> FlowResult:
        """Шаг 2: Ввод базовых сетевых параметров Универсального сервера."""
        errors = {}
        if user_input is not None:
            self._generic_data = user_input
            if user_input.get("auth_type") == "key":
                return await self.async_step_generic_key()
            return await self.async_step_generic_password()

        return self.async_show_form(
            step_id="generic",
            data_schema=vol.Schema({
                vol.Required("server_name", default=DEFAULT_SERVER_NAME): str,
                vol.Required("server_ip", default=DEFAULT_SERVER_IP): str,
                vol.Required("server_port", default=DEFAULT_SERVER_PORT): int,
                vol.Required("server_user", default=DEFAULT_SERVER_USER): str,
                vol.Required("auth_type", default="key"): vol.In([
                    "key",
                    "password"
                ])
            }),
            errors=errors
        )

    async def async_step_generic_key(self, user_input=None) -> FlowResult:
        """Шаг 3а: Указание пути к SSH-ключу для Универсального сервера."""
        errors = {}
        if user_input is not None:
            data = {**self._generic_data, **user_input, "hub_type": "generic"}
            return self.async_create_entry(title=data["server_name"], data=data)

        return self.async_show_form(
            step_id="generic_key",
            data_schema=vol.Schema({
                vol.Required("key_path", default=DEFAULT_KEY_PATH): str
            }),
            errors=errors
        )

    async def async_step_generic_password(self, user_input=None) -> FlowResult:
        """Шаг 3б: Ввод пароля пользователя для Универсального сервера."""
        errors = {}
        if user_input is not None:
            data = {**self._generic_data, **user_input, "hub_type": "generic"}
            return self.async_create_entry(title=data["server_name"], data=data)

        return self.async_show_form(
            step_id="generic_password",
            data_schema=vol.Schema({
                vol.Required("server_password"): str
            }),
            errors=errors
        )
    async def async_step_immich(self, user_input=None) -> FlowResult:
        """Шаг 2: Ввод базовых параметров подключения для сервера Immich."""
        errors = {}
        if user_input is not None:
            self._generic_data = user_input
            return await self.async_step_immich_auth()

        return self.async_show_form(
            step_id="immich",
            data_schema=vol.Schema({
                vol.Required("server_name", default=DEFAULT_IMMICH_SERVER_NAME): str,
                vol.Required("server_ip", default=DEFAULT_SERVER_IP): str,
                vol.Required("server_port", default=DEFAULT_SERVER_PORT): int,
                vol.Required("server_user", default=DEFAULT_SERVER_USER): str,
                vol.Required("auth_type", default="key"): vol.In([
                    "key",
                    "password"
                ])
            }),
            errors=errors
        )

    async def async_step_immich_auth(self, user_input=None) -> FlowResult:
        """Шаг 3: Ввод секретов авторизации и параметров путей контейнера Immich."""
        errors = {}
        if user_input is not None:
            data = {**self._generic_data, **user_input, "hub_type": "immich"}
            data["immich_api_url"] = self._async_build_api_url(data)
            return self.async_create_entry(title=data["server_name"], data=data)

        fields = {}
        if self._generic_data.get("auth_type") == "password":
            fields[vol.Required("server_password")] = str
        else:
            fields[vol.Required("key_path", default=DEFAULT_KEY_PATH)] = str

        fields.update({
            vol.Required("immich_remote_port", default=2283): int,
            vol.Required("immich_ssl", default=False): bool,
            vol.Required("immich_api_key"): str,
            vol.Required("immich_compose_path", default=DEFAULT_IMMICH_COMPOSE_PATH): str,
            vol.Required("immich_backup_path", default=DEFAULT_IMMICH_BACKUP_PATH): str,
            vol.Required("immich_db_user", default=DEFAULT_IMMICH_DB_USER): str,
        })

        return self.async_show_form(
            step_id="immich_auth",
            data_schema=vol.Schema(fields),
            errors=errors
        )

    async def async_step_reconfigure(self, user_input=None) -> FlowResult:
        """Шаг изменения параметров работающего хаба через кнопку в GUI."""
        errors = {}
        entry = self.hass.config_entries.async_get_entry(self.context["entry_id"])
        current_data = entry.data
        hub_type = current_data.get("hub_type", "generic")

        if user_input is not None:
            new_data = {**current_data, **user_input}
            if hub_type == "immich":
                new_data["immich_api_url"] = self._async_build_api_url(new_data)
            return self.async_update_reload_and_abort(entry, data=new_data)

        fields = {
            vol.Required("server_ip", default=current_data.get("server_ip", DEFAULT_SERVER_IP)): str,
            vol.Required("server_port", default=current_data.get("server_port", DEFAULT_SERVER_PORT)): int,
            vol.Required("server_user", default=current_data.get("server_user", DEFAULT_SERVER_USER)): str,
        }

        if current_data.get("auth_type") == "password":
            fields[vol.Required("server_password", default=current_data.get("server_password", ""))]: str
        else:
            fields[vol.Required("key_path", default=current_data.get("key_path", DEFAULT_KEY_PATH))]: str

        if hub_type == "immich":
            fields.update({
                vol.Required("immich_remote_port", default=current_data.get("immich_remote_port", 2283)): int,
                vol.Required("immich_ssl", default=current_data.get("immich_ssl", False)): bool,
                vol.Required("immich_api_key", default=current_data.get("immich_api_key", "")): str,
                vol.Required("immich_compose_path", default=current_data.get("immich_compose_path", DEFAULT_IMMICH_COMPOSE_PATH)): str,
                vol.Required("immich_backup_path", default=current_data.get("immich_backup_path", DEFAULT_IMMICH_BACKUP_PATH)): str,
                vol.Required("immich_db_user", default=current_data.get("immich_db_user", DEFAULT_IMMICH_DB_USER)): str,
            })

        return self.async_show_form(
            step_id="reconfigure",
            data_schema=vol.Schema(fields),
            errors=errors
        )

    def _async_build_api_url(self, data: dict) -> str:
        """Внутренний вспомогательный метод сборки правильного URL для REST API Immich."""
        ip = data.get("server_ip", DEFAULT_SERVER_IP)
        port = data.get("immich_remote_port", 2283)
        prefix = PREFIX_HTTPS if data.get("immich_ssl") else PREFIX_HTTP
        return f"{prefix}{ip}:{port}"

    @staticmethod
    @callback
    def async_get_options_flow(config_entry):
        """Перенаправление на обработчик изменения опций (шестеренку)."""
        return SSHServerControlOptionsFlowHandler(config_entry)
