import asyncio
import logging
from homeassistant.core import HomeAssistant
from homeassistant.config_entries import ConfigEntry

from .const import (
    DOMAIN,
    DEFAULT_SERVER_IP,
    DEFAULT_SERVER_PORT,
    DEFAULT_SERVER_USER,
    DEFAULT_KEY_PATH,
    DEFAULT_SERVER_PASSWORD
)

_LOGGER = logging.getLogger(__name__)

async def async_run_ssh_command(
    command: str, 
    wait_for_result: bool = True, 
    hass: HomeAssistant = None, 
    entry: ConfigEntry = None
) -> str:
    """Универсальная функция для выполнения команд по SSH (ключ / пароль)."""
    ip = DEFAULT_SERVER_IP
    port = DEFAULT_SERVER_PORT
    user = DEFAULT_SERVER_USER
    auth_type = "key"
    key = DEFAULT_KEY_PATH
    password = DEFAULT_SERVER_PASSWORD

    target_entry = entry
    if not target_entry and hass:
        entries = hass.config_entries.async_entries(DOMAIN)
        if entries:
            target_entry = entries[0]  # Исправлено: берем первый объект записи из списка, а не весь список

    if target_entry:
        ip = target_entry.data.get("server_ip", ip)
        port = target_entry.data.get("server_port", port)
        user = target_entry.data.get("server_user", user)
        auth_type = target_entry.data.get("auth_type", auth_type)
        key = target_entry.data.get("key_path", key)
        password = target_entry.data.get("server_password", password)

    # Оптимизируем параметры для приставки Tanix (отключаем лишние обмены ключами)
    ssh_options = [
        "-q",  # Полностью глушит вывод баннеров операционной системы при входе
        "-o", "StrictHostKeyChecking=no", 
        "-o", "ConnectTimeout=5",
        "-p", str(port)
    ]

    if auth_type == "password" and password:
        ssh_base = ["sshpass", "-p", password, "ssh"] + ssh_options + [f"{user}@{ip}", command]
    else:
        ssh_base = ["ssh", "-i", key] + ssh_options + [f"{user}@{ip}", command]

    try:
        proc = await asyncio.create_subprocess_exec(
            *ssh_base,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )

        if not wait_for_result:
            return "Запущено"

        # Ограничиваем общее время выполнения команды, чтобы не вешать треды HA
        stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=300)

        if proc.returncode == 0 and stdout:
            return stdout.decode().strip()
        elif stderr:
            _LOGGER.debug(f"SSH команда [{command}] на {ip}:{port} вернула stderr: {stderr.decode().strip()}")

    except asyncio.TimeoutError:
        _LOGGER.warning(f"Таймаут выполнения команды SSH [{command}] на {ip}:{port}")
    except Exception as err:
        _LOGGER.error(f"Не удалось выполнить SSH команду [{command}] on {ip}:{port}: {err}")

    return ""
