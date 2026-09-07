import logging
from homeassistant.core import HomeAssistant
from homeassistant.config_entries import ConfigEntry
from homeassistant.helpers import device_registry as dr

from .const import DOMAIN, CONF_SERVER_NAME
from .ssh_client import async_run_ssh_command

_LOGGER = logging.getLogger(__name__)

async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Запуск конкретного экземпляра SSH сервера."""
    server_name = entry.data.get(CONF_SERVER_NAME, "Linux Server")
    _LOGGER.info(f"Инициализация сервера '{server_name}'. Запрашиваю системные данные...")

    # Передаем текущий entry в клиент, чтобы опрашивать именно этот сервер на его порту
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

    # Если связи нет, выводим красивую нейтральную заглушку вместо упоминания Debian
    if not os_version:
        os_version = "Недоступен (Ошибка связи по SSH)"

    if not hw_raw or hw_raw.startswith(","):
        uname_m = await async_run_ssh_command("uname -m", hass=hass, entry=entry)
        free_m = await async_run_ssh_command("free -h | grep Mem | awk '{print $2}'", hass=hass, entry=entry)
        hw_version = f"{uname_m}, {free_m} RAM" if uname_m else "Неизвестная архитектура"
    else:
        hw_version = hw_raw

    # Регистрируем уникальное устройство для этого конкретного хаба
    device_registry = dr.async_get(hass)
    device_registry.async_get_or_create(
        config_entry_id=entry.entry_id,
        # Уникальный ID устройства теперь жестко привязан к ID интеграции, что позволяет создавать много серверов
        identifiers={(DOMAIN, f"server_{entry.entry_id}")},
        name=server_name,
        manufacturer="Linux",
        model="SSH Server",
        sw_version=os_version,
        hw_version=hw_version
    )

    # Регистрируем глобальный прослушиватель обновлений опций для этой записи
    entry.async_on_unload(entry.add_update_listener(async_reload_entry))

    # Перенаправляем запуск на платформы
    await hass.config_entries.async_forward_entry_setups(entry, ["sensor", "button"])
    return True

async def async_reload_entry(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Мягкий перезапуск конкретного сервера при изменении его кнопок/сенсоров."""
    _LOGGER.info(f"Настройки сервера '{entry.data.get(CONF_SERVER_NAME)}' изменены. Перезагрузка...")
    await hass.config_entries.async_reload(entry.entry_id)

async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Разгрузка сервера."""
    return await hass.config_entries.async_unload_platforms(entry, ["sensor", "button"])
