import logging
from homeassistant.core import HomeAssistant
from homeassistant.config_entries import ConfigEntry
from homeassistant.helpers import device_registry as dr

from .const import DOMAIN, DEFAULT_IMMICH_SERVER_NAME, DEFAULT_SERVER_NAME
from .ssh_client import async_run_ssh_command

_LOGGER = logging.getLogger(__name__)

async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Запуск конкретного экземпляра хаба (Универсальный или единый Immich через SSH)."""
    hub_type = entry.data.get("hub_type", "generic")
    
    if DOMAIN not in hass.data:
        hass.data[DOMAIN] = {}
    
    hass.data[DOMAIN][f"force_{entry.entry_id}"] = False
    hass.data[DOMAIN][f"updating_status_{entry.entry_id}"] = ""

    if hub_type == "immich" and not entry.options:
        from .const import (
            DEFAULT_IMMICH_UPDATE_VALUE_TEMPLATE, 
            DEFAULT_IMMICH_UPDATE_AVAIL_TEMPLATE,
            DEFAULT_IMMICH_FORCE_AVAIL_TEMPLATE
        )
        init_options = {
            "immich_backup_keep_days": 14,
            "immich_backup_keep_count": 5,
            "sensors": {
                "immich_update": {
                    "name": "Immich Update",
                    "command": "__api_immich_update__",
                    "value_template": DEFAULT_IMMICH_UPDATE_VALUE_TEMPLATE,
                    "scan_interval": 86400,
                    "category": "main"
                }
            },
            "buttons": {
                "immich_run_update": {
                    "name": "Immich Run Update",
                    "command": "__api_immich_run_update_sequence__",
                    "availability_template": DEFAULT_IMMICH_UPDATE_AVAIL_TEMPLATE,
                    "wait_for_result": False,
                    "category": "diagnostic"
                }
            },
            "switches": {
                "immich_force_mode": {
                    "name": "Immich Force Mode",
                    "availability_template": DEFAULT_IMMICH_FORCE_AVAIL_TEMPLATE,
                    "category": "diagnostic"
                }
            }
        }
        hass.config_entries.async_update_entry(entry, options=init_options)

    if hub_type == "immich":
        server_name = entry.data.get("server_name", DEFAULT_IMMICH_SERVER_NAME)
        manufacturer = "Immich"
        model = "Photo Hosting Hub"
    else:
        server_name = entry.data.get("server_name", DEFAULT_SERVER_NAME)
        manufacturer = "Linux"
        model = "SSH Server"

    _LOGGER.info(f"Инициализация хаба '{server_name}' [Тип: {hub_type}]. Запрашиваю системные данные...")

    os_version = await async_run_ssh_command(
        "cat /etc/os-release | grep PRETTY_NAME | cut -d'=' -f2 | tr -d '\"'", 
        hass=hass, 
        entry=entry
    )
    hw_raw = await async_run_ssh_command(
        "echo \"$(lscpu | grep Architecture | awk '{print $2}'), $(free -h | grep Mem | awk '{print $2}') RAM\"", 
        hass=hass, 
        entry=entry
    )

    if not os_version:
        os_version = "unknown_os"

    if not hw_raw or hw_raw.startswith(","):
        uname_m = await async_run_ssh_command("uname -m", hass=hass, entry=entry)
        free_m = await async_run_ssh_command("free -h | grep Mem | awk '{print $2}'", hass=hass, entry=entry)
        hw_version = f"{uname_m}, {free_m} RAM" if uname_m else "unknown_arch"
    else:
        hw_version = hw_raw

    device_registry = dr.async_get(hass)
    device_registry.async_get_or_create(
        config_entry_id=entry.entry_id,
        identifiers={(DOMAIN, f"server_{entry.entry_id}")},
        name=server_name,
        manufacturer=manufacturer,
        model=model,
        sw_version=os_version,
        hw_version=hw_version
    )

    entry.async_on_unload(entry.add_update_listener(async_reload_entry))

    await hass.config_entries.async_forward_entry_setups(entry, ["sensor", "button", "switch"])
    return True

async def async_reload_entry(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Мягкий перезапуск хаба при изменении параметров."""
    _LOGGER.info(f"Настройки хаба изменены. Перезагрузка записи {entry.entry_id}...")
    await hass.config_entries.async_reload(entry.entry_id)

async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Разгрузка хаба из системы."""
    return await hass.config_entries.async_unload_platforms(entry, ["sensor", "button", "switch"])
