# --- dynamic_sensor.py (Исправленная Часть 1) ---
import json
import logging
from datetime import timedelta

from homeassistant.components.sensor import SensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import template as template_helper, entity_registry as er
from homeassistant.helpers.entity import EntityCategory
from homeassistant.helpers.event import async_track_time_interval
from homeassistant.util import dt as dt_util

from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .const import DOMAIN, DEFAULT_IMMICH_UPDATE_VALUE_TEMPLATE
from .ssh_client import async_run_ssh_command

_LOGGER = logging.getLogger(__name__)

class TanixDynamicSensor(SensorEntity):
    """Класс динамического сенсора со свободной перезаписью состояний шаблонами."""

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry, sensor_id: str, config: dict) -> None:
        """Инициализация сущности сенсора."""
        self.hass = hass
        self._entry = entry
        self._sensor_id = sensor_id
        self._config = config
        
        self._attr_name = config.get("name", sensor_id)
        self._attr_unique_id = f"ssh_srv_{entry.entry_id}_snr_{sensor_id}"
        self.entity_id = f"sensor.ssh_server_{entry.title.lower().replace(' ', '_')}_{sensor_id}"
        
        self._remove_timer = None
        self._custom_attributes = {}
        
        unit = config.get("unit_of_measurement", "").strip() or None
        self._attr_native_unit_of_measurement = unit

        if unit:
            self._attr_native_value = None
        else:
            self._attr_native_value = "checking"

        has_template = bool(config.get("value_template", "").strip())

        # ТЗ: Разрешаем системным датчикам Immich всегда использовать свои персональные словари переводов
        if sensor_id in ["immich_status", "immich_update"]:
            self._attr_translation_key = sensor_id
        else:
            self._attr_translation_key = "custom_sensor"


        if config.get("category") == "diagnostic":
            self._attr_entity_category = EntityCategory.DIAGNOSTIC
        else:
            self._attr_entity_category = None

        self._attr_device_info = {"identifiers": {(DOMAIN, f"server_{entry.entry_id}")}}

    @property
    def icon(self) -> str | None:
        """Динамическая смена тематических иконок в зависимости от фазы работы и обновления."""
        if self._sensor_id == "immich_update":
            return "mdi:github"
        if self._sensor_id == "immich_last_check":
            return "mdi:clock-check-outline"
            
        if self._sensor_id == "immich_status":
            state = self._attr_native_value
            
            if state == "backup":
                return "mdi:database-arrow-up"
            elif state == "pulling":
                return "mdi:cloud-download-outline"
            elif state == "restarting":
                return "mdi:restart"
            elif state == "pruning":
                return "mdi:broom"
            elif state == "success":
                return "mdi:check-circle-outline"
            elif state == "error":
                return "mdi:alert-circle-outline"
            
            return "mdi:docker"

        return "mdi:eye"

    @property
    def should_poll(self) -> bool:
        """ТЗ: Защита от блокировки GitHub API. Поллинг ядра HA строго выключен!"""
        return False

    @property
    def extra_state_attributes(self) -> dict:
        """Передача атрибутов в систему."""
        return self._custom_attributes

    async def async_added_to_hass(self) -> None:
        """Запуск реактивных подписок или изолированных таймеров опроса."""
        command = self._config.get("command", "").strip()
        value_template = self._config.get("value_template", "").strip()

        if not command and value_template:
            ent_reg = er.async_get(self.hass)
            up_sid = ent_reg.async_get_entity_id("sensor", DOMAIN, f"ssh_srv_{self._entry.entry_id}_snr_immich_update") or f"sensor.ssh_server_{self._entry.title.lower().replace(' ', '_')}_immich_update"

            @callback
            def _async_sensor_template_listener(event, updates):
                """Срабатывает мгновенно и реактивно при любом обновлении атрибутов."""
                # ТЗ: Правильно и безопасно извлекаем объект результата из списка обновлений ядра HA
                if updates and len(updates) > 0:
                    last_result = updates[-1].result
                    if last_result is not None and str(last_result).strip() != "":
                        self._attr_native_value = str(last_result)
                        _LOGGER.debug(f"⏰ [РЕАКТИВНЫЙ ДАТЧИК CHECK] Время проверки обновилось в GUI: {self._attr_native_value}")
                        self.async_write_ha_state()

            from homeassistant.helpers.event import async_track_template_result, TrackTemplate
            self.async_on_remove(
                async_track_template_result(
                    self.hass,
                    [TrackTemplate(template_helper.Template(value_template, self.hass), {"entity_id": self.entity_id, "up_entity_id": up_sid})],
                    _async_sensor_template_listener,
                )
            )
            return

        self.hass.async_create_task(self.async_update())
        
        scan_interval = max(int(self._config.get("scan_interval", 30)), 5)
        
        @callback
        def _timer_trigger(now):
            self.hass.async_create_task(self.async_update())

        self._remove_timer = async_track_time_interval(
            self.hass, _timer_trigger, timedelta(seconds=scan_interval)
        )


# --- dynamic_sensor.py (Часть 2 из 2) ---

    async def async_update(self) -> None:
        """Выполнение макроса или SSH команды."""
        command = self._config.get("command", "").strip()
        if not command:
            return

        if command.startswith("__") and command.endswith("__"):
            await self._execute_internal_macro(command)
            return

        raw_result = await async_run_ssh_command(command, wait_for_result=True, hass=self.hass, entry=self._entry)
        
        if raw_result == "" or raw_result is None:
            self._attr_native_value = None if self._attr_native_unit_of_measurement else "connection_error"
            self._custom_attributes = {}
            self.async_write_ha_state()
            return

        processed_value = raw_result
        try:
            json_data = json.loads(raw_result)
            if isinstance(json_data, dict) and "state" in json_data:
                processed_value = json_data.get("state", "")
                self._custom_attributes = json_data.get("attributes", {})
            else:
                self._custom_attributes = {}
        except (json.JSONDecodeError, TypeError):
            self._custom_attributes = {}

        value_template = self._config.get("value_template", "").strip()
        if value_template:
            try:
                tpl = template_helper.Template(value_template, self.hass)
                self._attr_native_value = tpl.async_render(variables={"value": processed_value, "entity_id": self.entity_id}, parse_result=True)
            except Exception as err:
                _LOGGER.error(f"Ошибка шаблона состояния {self._attr_name}: {err}")
                self._attr_native_value = None if self._attr_native_unit_of_measurement else "template_error"
        else:
            self._attr_native_value = processed_value

        self.async_write_ha_state()

    async def _execute_internal_macro(self, macro_cmd: str) -> None:
        """Прямая обработка встроенных макросов на Python."""
        current_time = dt_util.now().strftime("%d.%m %H:%M:%S")
        entry_id = self._entry.entry_id

        # МАКРОС СТАТУСА IMMICH
        if macro_cmd == "__api_immich_status__":
            if DOMAIN in self.hass.data and self.hass.data[DOMAIN].get(f"updating_status_{entry_id}"):
                self._attr_native_value = self.hass.data[DOMAIN][f"updating_status_{entry_id}"]
                self.async_write_ha_state()
                return

            from .immich_api import async_get_container_status, async_get_active_jobs
            docker_status = await async_get_container_status(self.hass, self._entry)
            
            active_jobs, api_online = await async_get_active_jobs(self.hass, self._entry)
            container_running = False

            if not docker_status or docker_status == "not_found":
                self._attr_native_value = "not_found"
            elif "unhealthy" in docker_status or "Exited" in docker_status:
                self._attr_native_value = "stopped"
            elif "starting" in docker_status:
                self._attr_native_value = "starting"
            elif "healthy" in docker_status or "Up" in docker_status:
                self._attr_native_value = "busy" if active_jobs > 0 else "running"
                container_running = True
            else:
                self._attr_native_value = "stopped"

            # ТЗ: Записываем только чистые данные. Подписанная кнопка среагирует сама на уровне ядра HA!
            self._custom_attributes = {
                "last_check_time": current_time,
                "container_is_running": container_running,
                "api_is_online": api_online
            }
            self.async_write_ha_state()

        # МАКРОС ОБНОВЛЕНИЙ IMMICH
        elif macro_cmd == "__api_immich_update__":
            _LOGGER.info("🚀 [ЗАПРОС GITHUB] Регламентный запрос обновлений.")
            from .immich_api import async_get_local_version, async_get_container_status
            from .const import URL_GITHUB_API
            
            docker_status = await async_get_container_status(self.hass, self._entry)
            container_running = "healthy" in docker_status or "Up" in docker_status
            
            local_ver = await async_get_local_version(self.hass, self._entry)
            remote_ver = ""
            is_breaking = False

            if local_ver and container_running:
                headers = {"User-Agent": "HomeAssistant-SSH-Server-Control", "Accept": "application/vnd.github.v3+json"}
                try:
                    session = async_get_clientsession(self.hass)
                    async with session.get(URL_GITHUB_API, headers=headers, timeout=7) as response:
                        if response.status == 200:
                            data = await response.json()
                            remote_ver = data.get("tag_name", local_ver)
                            is_breaking = "breaking change" in data.get("body", "").lower()
                except Exception as err:
                    _LOGGER.warning(f"GitHub API error: {err}")

            # ИСХОД 1: Контейнер работает, но ошибка сети с GitHub
            if container_running and not remote_ver:
                self._attr_native_value = "network_error"
                # ТЗ: Убираем лишние дублирующие атрибуты контейнера и API
                self._custom_attributes = {"last_check_time": current_time}
                self.async_write_ha_state()
                return
                
            # ИСХОД 2: Контейнер полностью лежит
            elif not container_running:
                self._attr_native_value = "checking"
                # ТЗ: Оставляем только базовый флаг отсутствия апдейта
                self._custom_attributes = {"last_check_time": current_time, "update_available": False}
                self.async_write_ha_state()
                return

            is_update_available = local_ver != remote_ver
            raw_state = "update_available_breaking" if is_breaking else ("update_available" if is_update_available else "up_to_date")
            display_version_str = f"{local_ver} -> {remote_ver}" if is_update_available else local_ver

            status_sid = ""
            force_sid = ""
            try:
                ent_reg = er.async_get(self.hass)
                status_sid = ent_reg.async_get_entity_id("sensor", DOMAIN, f"ssh_srv_{entry_id}_snr_immich_status") or ""
                force_sid = ent_reg.async_get_entity_id("switch", DOMAIN, f"ssh_srv_{entry_id}_immich_force_mode") or ""
            except Exception as e:
                _LOGGER.error(f"Ошибка маппинга связанных ID: {e}")

            # ИСХОД 3: Успешная проверка версии (Найдите блок заполнения атрибутов ниже и очистите его)
            self._custom_attributes = {
                "last_check_time": current_time,
                "update_available": is_update_available,
                "breaking_changes": is_breaking,
                "local_version": local_ver,
                "latest_version": remote_ver,
                "display_version": display_version_str,
                "status_entity_id": status_sid,
                "force_mode_entity_id": force_sid
            }

            options_sensors = self._entry.options.get("sensors", {})
            value_template = options_sensors.get("immich_update", {}).get("value_template", "").strip()

            if value_template:
                try:
                    tpl = template_helper.Template(value_template, self.hass)
                    self._attr_native_value = tpl.async_render(variables={"value": raw_state, "display_version": display_version_str, "update_available": is_update_available}, parse_result=True)
                except Exception as err:
                    self._attr_native_value = raw_state
            else:
                self._attr_native_value = raw_state
            
            # ТЗ: Код полностью очищен от вызовов сторонних обновлений. Полная реактивность!
            self.async_write_ha_state()

        # МАКРОС ВРЕМЕНИ ПОСЛЕДНЕЙ ПРОВЕРКИ
        elif macro_cmd == "__api_immich_last_check__":
            try:
                ent_reg = er.async_get(self.hass)
                update_sid = ent_reg.async_get_entity_id("sensor", DOMAIN, f"ssh_srv_{entry_id}_snr_immich_update")
                if update_sid:
                    update_state = self.hass.states.get(update_sid)
                    if update_state and "last_check_time" in update_state.attributes:
                        self._attr_native_value = update_state.attributes["last_check_time"]
                    else:
                        self._attr_native_value = None
                else:
                    self._attr_native_value = None
            except Exception:
                self._attr_native_value = None
            self.async_write_ha_state()

    async def async_will_remove_from_hass(self) -> None:
        """Чистим таймеры."""
        if self._remove_timer:
            self._remove_timer()
