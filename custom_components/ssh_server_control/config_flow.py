import voluptuous as vol
from homeassistant import config_entries
from homeassistant.core import callback
from homeassistant.data_entry_flow import FlowResult

from .const import (
    DOMAIN,
    DEFAULT_SERVER_NAME,
    DEFAULT_SERVER_IP,
    DEFAULT_SERVER_PORT,
    DEFAULT_SERVER_USER,
    DEFAULT_KEY_PATH,
    CONF_SERVER_NAME,
    CONF_SERVER_IP,
    CONF_SERVER_PORT,
    CONF_SERVER_USER,
    CONF_KEY_PATH,
)

class SshServerControlConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Класс для первоначальной настройки и перенастройки SSH серверов."""
    VERSION = 1

    async def async_step_user(self, user_input=None) -> FlowResult:
        """Срабатывает при добавлении нового сервера через GUI (разрешено многократно)."""
        if user_input is not None:
            # Используем имя сервера в качестве заголовка интеграции на экране
            return self.async_create_entry(title=user_input[CONF_SERVER_NAME], data=user_input)

        # Форма начальной настройки сервера
        data_schema = vol.Schema(
            {
                vol.Required(CONF_SERVER_NAME, default=DEFAULT_SERVER_NAME): str,
                vol.Required(CONF_SERVER_IP, default=DEFAULT_SERVER_IP): str,
                vol.Required(CONF_SERVER_PORT, default=DEFAULT_SERVER_PORT): int,
                vol.Required(CONF_SERVER_USER, default=DEFAULT_SERVER_USER): str,
                vol.Required(CONF_KEY_PATH, default=DEFAULT_KEY_PATH): str,
            }
        )

        return self.async_show_form(step_id="user", data_schema=data_schema)

    async def async_step_reconfigure(self, user_input=None) -> FlowResult:
        """Срабатывает при выборе пункта 'Перенастроить' в меню трех точек конкретного сервера."""
        reconfigure_entry = self._get_reconfigure_entry()
        
        if user_input is not None:
            return self.async_update_reload_and_abort(
                reconfigure_entry,
                data={**reconfigure_entry.data, **user_input}
            )

        # Подтягиваем текущие сохраненные данные этого конкретного сервера
        current_name = reconfigure_entry.data.get(CONF_SERVER_NAME, DEFAULT_SERVER_NAME)
        current_ip = reconfigure_entry.data.get(CONF_SERVER_IP, DEFAULT_SERVER_IP)
        current_port = reconfigure_entry.data.get(CONF_SERVER_PORT, DEFAULT_SERVER_PORT)
        current_user = reconfigure_entry.data.get(CONF_SERVER_USER, DEFAULT_SERVER_USER)
        current_key = reconfigure_entry.data.get(CONF_KEY_PATH, DEFAULT_KEY_PATH)

        data_schema = vol.Schema(
            {
                vol.Required(CONF_SERVER_NAME, default=current_name): str,
                vol.Required(CONF_SERVER_IP, default=current_ip): str,
                vol.Required(CONF_SERVER_PORT, default=current_port): int,
                vol.Required(CONF_SERVER_USER, default=current_user): str,
                vol.Required(CONF_KEY_PATH, default=current_key): str,
            }
        )

        return self.async_show_form(step_id="reconfigure", data_schema=data_schema)

    @staticmethod
    @callback
    def async_get_options_flow(config_entry: config_entries.ConfigEntry) -> config_entries.OptionsFlow:
        """Связываем ConfigFlow с OptionsFlow (нажатие на шестерёнку)."""
        from .options_flow import SshServerControlOptionsFlowHandler
        return SshServerControlOptionsFlowHandler(config_entry)
