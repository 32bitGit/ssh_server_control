import logging
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DEFAULT_IMMICH_BUTTONS_CONF
from .dynamic_button import TanixDynamicButton

_LOGGER = logging.getLogger(__name__)

async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Запуск платформы кнопок."""
    hub_type = entry.data.get("hub_type", "generic")
    options_buttons = entry.options.get("buttons", {})
    new_entities = []

    # Если тип хаба Immich — гарантируем создание двух нативных встроенных кнопок
    if hub_type == "immich":
        # 1. Кнопка проверки обновлений
        check_config = options_buttons.get(
            "immich_check_update", 
            DEFAULT_IMMICH_BUTTONS_CONF["immich_check_update"]
        )
        new_entities.append(TanixDynamicButton(hass, entry, "immich_check_update", check_config))

        # 2. Кнопка выполнения обновлений
        run_config = options_buttons.get(
            "immich_run_update", 
            DEFAULT_IMMICH_BUTTONS_CONF["immich_run_update"]
        )
        new_entities.append(TanixDynamicButton(hass, entry, "immich_run_update", run_config))

    # Загружаем все остальные пользовательские кнопки из настроек шестеренки
    if options_buttons:
        for b_id, b_data in options_buttons.items():
            if b_id in ["immich_check_update", "immich_run_update"]:
                continue
            new_entities.append(TanixDynamicButton(hass, entry, b_id, b_data))

    if new_entities:
        async_add_entities(new_entities)
