import asyncio
import logging
from homeassistant.core import HomeAssistant
from homeassistant.config_entries import ConfigEntry

from .const import DOMAIN, CONF_SERVER_IP, CONF_SERVER_PORT, CONF_SERVER_USER, CONF_KEY_PATH

_LOGGER = logging.getLogger(__name__)

async def async_run_ssh_command(
    command: str, 
    wait_for_result: bool = True, 
    hass: HomeAssistant = None, 
    entry: ConfigEntry = None
) -> str:
    """Универсальная функция для выполнения команд на удаленном сервере по SSH."""
    # Значения по умолчанию
    ip = "127.0.0.1"
    port = 22
    user = "root"
    key = "/config/.ssh/id_rsa"

    # Если передан конкретный entry (из __init__ или сущностей), берем его сетевые настройки
    target_entry = entry
    if not target_entry and hass:
        # Если передан только hass, пытаемся взять первую запись (для обратной совместимости)
        entries = hass.config_entries.async_entries(DOMAIN)
        if entries:
            target_entry = entries[0]

    if target_entry:
        ip = target_entry.data.get(CONF_SERVER_IP, ip)
        port = target_entry.data.get(CONF_SERVER_PORT, port)
        user = target_entry.data.get(CONF_SERVER_USER, user)
        key = target_entry.data.get(CONF_KEY_PATH, key)

    # Формируем шаблон подключения с флагом кастомного порта -p
    ssh_base = [
        "ssh", 
        "-o", "StrictHostKeyChecking=no", 
        "-o", "ConnectTimeout=5",
        "-p", str(port),
        "-i", key, 
        f"{user}@{ip}", 
        command
    ]

    try:
        proc = await asyncio.create_subprocess_exec(
            *ssh_base,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )

        if not wait_for_result:
            _LOGGER.debug(f"Команда SSH запущена в фоновом режиме: {command}")
            return "Запущено в фоне"

        stdout, stderr = await proc.communicate()

        if proc.returncode == 0 and stdout:
            return stdout.decode().strip()
        elif stderr:
            _LOGGER.warning(f"SSH команда [{command}] на {ip}:{port} вернула ошибку: {stderr.decode().strip()}")

    except Exception as err:
        _LOGGER.error(f"Не удалось выполнить SSH команду [{command}] на {ip}:{port}: {err}")

    return ""
