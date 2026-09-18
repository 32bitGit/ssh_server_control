import logging
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DEFAULT_IMMICH_SENSORS_CONF
from .dynamic_sensor import TanixDynamicSensor

_LOGGER = logging.getLogger(__name__)

async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Запуск платформы датчиков с учетом категорий из опций."""
    hub_type = entry.data.get("hub_type", "generic")
    options_sensors = entry.options.get("sensors", {})
    new_entities = []

    # Если тип хаба Immich — гарантируем инициализацию трех системных датчиков
    if hub_type == "immich":
        # 1. Датчик Статуса
        status_config = options_sensors.get(
            "immich_status", 
            DEFAULT_IMMICH_SENSORS_CONF["immich_status"]
        )
        new_entities.append(TanixDynamicSensor(hass, entry, "immich_status", status_config))

        # 2. Датчик Обновлений
        update_config = options_sensors.get(
            "immich_update", 
            DEFAULT_IMMICH_SENSORS_CONF["immich_update"]
        )
        new_entities.append(TanixDynamicSensor(hass, entry, "immich_update", update_config))

        # 3. Датчик Времени Последней Проверки
        last_check_config = options_sensors.get(
            "immich_last_check", 
            DEFAULT_IMMICH_SENSORS_CONF["immich_last_check"]
        )
        new_entities.append(TanixDynamicSensor(hass, entry, "immich_last_check", last_check_config))

    # Загружаем все остальные кастомные датчики из настроек шестеренки
    if options_sensors:
        for s_id, s_data in options_sensors.items():
            if s_id in ["immich_status", "immich_update", "immich_last_check"]:
                continue
            new_entities.append(TanixDynamicSensor(hass, entry, s_id, s_data))

    if new_entities:
        async_add_entities(new_entities)
