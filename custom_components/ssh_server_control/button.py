import logging
from homeassistant.components.button import ButtonEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers import template as template_helper

from .const import DOMAIN, CONF_BUTTONS
from .ssh_client import async_run_ssh_command

_LOGGER = logging.getLogger(__name__)

async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Запуск платформы динамических кнопок для конкретного SSH сервера."""
    options_buttons = entry.options.get(CONF_BUTTONS, {})
    new_entities = []

    for b_id, b_data in options_buttons.items():
        _LOGGER.info(f"Регистрация кнопки для сервера [{entry.title}]: {b_id} ({b_data.get('name')})")
        new_entities.append(TanixDynamicButton(hass, entry, b_id, b_data))

    if new_entities:
        async_add_entities(new_entities)


class TanixDynamicButton(ButtonEntity):
    """Класс стандартной кнопки с SSH-командой и поддержкой Jinja-доступности."""

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry, button_id: str, config: dict) -> None:
        """Инициализация сущности."""
        self.hass = hass
        self._entry = entry
        self._button_id = button_id
        self._config = config
        
        self._attr_name = config.get("name", "Кнопка")
        # Делаем уникальный ID сущности глобально уникальным (включая ID сервера)
        self._attr_unique_id = f"ssh_srv_{entry.entry_id}_btn_{button_id}"
        self.entity_id = f"button.ssh_server_{entry.title.lower().replace(' ', '_')}_{button_id}"

        # Привязываем строго к текущему уникальному серверу
        self._attr_device_info = {
            "identifiers": {(DOMAIN, f"server_{entry.entry_id}")},
        }

    @property
    def available(self) -> bool:
        """Доступность полностью завязана на Jinja-шаблон из GUI."""
        jinja_template = self._config.get("availability_template", "").strip()
        if jinja_template:
            try:
                tpl = template_helper.Template(jinja_template, self.hass)
                return bool(tpl.async_render(parse_result=True))
            except Exception as err:
                _LOGGER.error(f"Ошибка шаблона доступности кнопки {self._attr_name}: {err}")
                return False
        return True

    async def async_press(self) -> None:
        """Срабатывает при нажатии на кнопку."""
        command = self._config.get("command", "")
        wait_for_result = self._config.get("wait_for_result", True)
        
        _LOGGER.info(f"Нажата кнопка [{self._attr_name}] на сервере [{self._entry.title}], отправляю команду...")
        # Явно передаем entry, чтобы команда знала IP и кастомный порт этого сервера
        await async_run_ssh_command(command, wait_for_result=wait_for_result, hass=self.hass, entry=self._entry)
