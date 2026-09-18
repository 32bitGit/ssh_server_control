# --- switch.py --- 
import logging
from homeassistant.components.switch import SwitchEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers import entity_registry as er, template as template_helper
from homeassistant.helpers.entity import EntityCategory

# ТЗ: Импортируем нативный трекер шаблонов для тумблера
from homeassistant.helpers.event import async_track_template_result, TrackTemplate

from .const import DOMAIN, DEFAULT_IMMICH_FORCE_AVAIL_TEMPLATE

_LOGGER = logging.getLogger(__name__)

async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Запуск платформы выключателей."""
    hub_type = entry.data.get("hub_type", "generic")
    new_entities = []

    if hub_type == "immich":
        _LOGGER.info(f"Регистрация защитного тумблера Immich для [{entry.title}]")
        new_entities.append(ImmichForceSwitch(hass, entry))

    if new_entities:
        # ТЗ: Чистый запуск БЕЗ каких-либо принудительных пинков кнопок в пустоту
        async_add_entities(new_entities)


class ImmichForceSwitch(SwitchEntity):
    """Тумблер временной разблокировки кнопки обновления с нативной реактивной доступностью."""

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        """Инициализация сущности."""
        self.hass = hass
        self._entry = entry
        self._attr_name = "Immich Force Mode"
        self._attr_unique_id = f"ssh_srv_{entry.entry_id}_immich_force_mode"
        self.entity_id = f"switch.ssh_server_{entry.title.lower().replace(' ', '_')}_immich_force_mode"
        
        self._attr_icon = "mdi:shield-alert"
        self._attr_device_info = {"identifiers": {(DOMAIN, f"server_{entry.entry_id}")}}
        
        # Внутренняя переменная нативной доступности тумблера
        self._template_available = False

        switches_options = entry.options.get("switches", {})
        switch_config = switches_options.get("immich_force_mode", {"category": "diagnostic"})
        
        if switch_config.get("category") == "main":
            self._attr_entity_category = None
        else:
            self._attr_entity_category = EntityCategory.DIAGNOSTIC

    @property
    def should_poll(self) -> bool:
        """Поллинг выключен, тумблер реактивно слушает события шаблона."""
        return False

    @property
    def is_on(self) -> bool:
        """Возвращает текущее состояние тумблера из оперативной памяти HA."""
        if DOMAIN in self.hass.data:
            return self.hass.data[DOMAIN].get(f"force_{self._entry.entry_id}", False)
        return False

    @property
    def available(self) -> bool:
        """Возвращает статус доступности, управляемый нативным трекером."""
        return self._template_available

# --- Изменение в switch.py ---

    async def async_added_to_hass(self) -> None:
        """Регистрация нативного слежения за шаблоном доступности тумблера."""
        switches_options = self._entry.options.get("switches", {})
        custom_template = switches_options.get("immich_force_mode", {}).get("availability_template", DEFAULT_IMMICH_FORCE_AVAIL_TEMPLATE).strip()

        ent_reg = er.async_get(self.hass)
        up_sid = ent_reg.async_get_entity_id("sensor", DOMAIN, f"ssh_srv_{self._entry.entry_id}_snr_immich_update") or f"sensor.ssh_server_{self._entry.title.lower().replace(' ', '_')}_immich_update"
        
        # Находим ID датчика статуса для передачи в шаблон тумблера
        st_sid = ent_reg.async_get_entity_id("sensor", DOMAIN, f"ssh_srv_{self._entry.entry_id}_snr_immich_status") or f"sensor.ssh_server_{self._entry.title.lower().replace(' ', '_')}_immich_status"

        @callback
        def _async_switch_template_listener(event, updates):
            """Срабатывает автоматически при изменении атрибутов."""
            result = updates.pop().result
            if isinstance(result, str):
                self._template_available = result.strip().lower() == "true"
            else:
                self._template_available = bool(result)
            _LOGGER.debug(f"🛡️ [НАТИВНЫЙ ТРЕКЕР ТУМБЛЕРА] Доступность пересчитана: {self._template_available}")
            self.async_write_ha_state()

        # Передаем в шаблон и up_entity_id, и status_entity_id (через переменные)
        self.async_on_remove(
            async_track_template_result(
                self.hass,
                [TrackTemplate(template_helper.Template(custom_template, self.hass), {"entity_id": self.entity_id, "up_entity_id": up_sid, "status_entity_id": st_sid})],
                _async_switch_template_listener,
            )
        )


    async def async_turn_on(self, **kwargs) -> None:
        """Срабатывает при включении тумблера пользователем в GUI."""
        _LOGGER.info(f"Режим Force Update принудительно ВКЛЮЧЕН для хаба [{self._entry.title}]")
        if DOMAIN not in self.hass.data:
            self.hass.data[DOMAIN] = {}
        self.hass.data[DOMAIN][f"force_{self._entry.entry_id}"] = True
        # ТЗ: Просто пишем стейт тумблера. Связанная кнопка САМА заметит это изменение благодаря своей подписке!
        self.async_write_ha_state()

    async def async_turn_off(self, **kwargs) -> None:
        """Срабатывает при выключении тумблера пользователем в GUI."""
        _LOGGER.info(f"Режим Force Update ВЫКЛЮЧЕН для хаба [{self._entry.title}]")
        if DOMAIN not in self.hass.data:
            self.hass.data[DOMAIN] = {}
        self.hass.data[DOMAIN][f"force_{self._entry.entry_id}"] = False
        # ТЗ: Кнопка сама закроется реактивно
        self.async_write_ha_state()
