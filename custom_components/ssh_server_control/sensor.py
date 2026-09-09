import logging
import json
from datetime import timedelta


from homeassistant.components.sensor import SensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers import template as template_helper
from homeassistant.helpers.entity import EntityCategory
from homeassistant.helpers.event import async_track_time_interval

from .const import DOMAIN, CONF_SENSORS
from .ssh_client import async_run_ssh_command

_LOGGER = logging.getLogger(__name__)

async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Запуск платформы динамических сенсоров для конкретного SSH сервера."""
    options_sensors = entry.options.get(CONF_SENSORS, {})
    new_entities = []

    for s_id, s_data in options_sensors.items():
        _LOGGER.info(f"Регистрация сенсора для сервера [{entry.title}]: {s_id} ({s_data.get('name')})")
        new_entities.append(TanixDynamicSensor(hass, entry, s_id, s_data))

    if new_entities:
        async_add_entities(new_entities)


class TanixDynamicSensor(SensorEntity):
    """Класс динамического сенсора с обработкой Jinja-шаблонов состояния."""

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry, sensor_id: str, config: dict) -> None:
        """Инициализация сущности сенсора."""
        self.hass = hass
        self._entry = entry
        self._sensor_id = sensor_id
        self._config = config
        
        self._attr_name = config.get("name", "Сенсор")
        self._attr_unique_id = f"ssh_srv_{entry.entry_id}_snr_{sensor_id}"
        self.entity_id = f"sensor.ssh_server_{entry.title.lower().replace(' ', '_')}_{sensor_id}"
        
        self._attr_native_value = None
        self._remove_timer = None
        
        # ВОЗВРАЩАЕМ: Словарь для хранения динамических атрибутов сущности
        self._custom_attributes = {}

        self._attr_native_unit_of_measurement = config.get("unit_of_measurement", "").strip() or None

        if config.get("category") == "diagnostic":
            self._attr_entity_category = EntityCategory.DIAGNOSTIC
        else:
            self._attr_entity_category = None

        # Привязываем строго к текущему уникальному серверу
        self._attr_device_info = {
            "identifiers": {(DOMAIN, f"server_{entry.entry_id}")},
        }

    @property
    def extra_state_attributes(self) -> dict:
        """ВОЗВРАЩАЕМ: Передача кастомных атрибутов в ядро Home Assistant."""
        return self._custom_attributes

    @property
    def available(self) -> bool:
        """Доступность сенсора на основе Jinja-шаблона из GUI."""
        jinja_template = self._config.get("availability_template", "").strip()
        if jinja_template:
            try:
                tpl = template_helper.Template(jinja_template, self.hass)
                return bool(tpl.async_render(parse_result=True))
            except Exception as err:
                _LOGGER.error(f"Ошибка шаблона доступности сенсора {self._attr_name}: {err}")
                return False
        return True

    async def async_added_to_hass(self) -> None:
        """Вызывается при регистрации сенсора в системе."""
        self.hass.async_create_task(self.async_update())

        scan_interval = max(int(self._config.get("scan_interval", 30)), 5)
        self._remove_timer = async_track_time_interval(
            self.hass,
            self._async_timer_trigger,
            timedelta(seconds=scan_interval)
        )

    async def _async_timer_trigger(self, now) -> None:
        """Триггер интервального таймера."""
        await self.async_update()

    async def async_update(self) -> None:
        """Метод сбора и форматирования данных сенсора."""
        command = self._config.get("command", "")
        if not command:
            return

        # Передаем сессию текущего entry, чтобы опрашивать правильный хост и порт
        raw_result = await async_run_ssh_command(command, wait_for_result=True, hass=self.hass, entry=self._entry)
        
        if raw_result is None or raw_result == "":
            self._attr_native_value = "Ошибка связи"
            self._custom_attributes = {} # Очищаем атрибуты при ошибке
            self.async_write_ha_state()
            return

        # --- ВОЗВРАЩАЕМ: МАГИЯ РАЗБОРА JSON-ОТВЕТА ---
        processed_value = raw_result
        try:
            # Пробуем распарсить вывод как JSON-словарь
            json_data = json.loads(raw_result)
            if isinstance(json_data, dict) and "state" in json_data:
                # Если структура наша (есть ключ "state"), забираем данные и словарь атрибутов
                processed_value = json_data.get("state", "")
                self._custom_attributes = json_data.get("attributes", {})
            else:
                # Если это валидный JSON, но структура не совпадает — сбрасываем атрибуты
                self._custom_attributes = {}
        except (json.JSONDecodeError, TypeError):
            # Если прилетел обычный текст (free -m, df -h), работаем в стандартном режиме
            self._custom_attributes = {}
        # --- КОНЕЦ МАГИИ РАЗБОРА JSON-ОТВЕТА ---

        value_template = self._config.get("value_template", "").strip()
        
        if value_template:
            try:
                tpl = template_helper.Template(value_template, self.hass)
                # Передаем в Jinja-шаблон уже очищенное от JSON-обертки значение processed_value
                formatted_value = tpl.async_render(variables={"value": processed_value}, parse_result=True)
                self._attr_native_value = formatted_value
            except Exception as err:
                _LOGGER.error(f"Ошибка шаблона состояния для сенсора {self._attr_name}: {err}")
                self._attr_native_value = "Ошибка шаблона"
        else:
            self._attr_native_value = processed_value

        self.async_write_ha_state()
