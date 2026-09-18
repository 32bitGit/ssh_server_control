# --- immich_api.py --- 
import logging
from homeassistant.core import HomeAssistant
from homeassistant.config_entries import ConfigEntry
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .const import PREFIX_HTTP, PREFIX_HTTPS, DEFAULT_SERVER_IP

_LOGGER = logging.getLogger(__name__)

async def async_get_container_status(hass: HomeAssistant, entry: ConfigEntry) -> str:
    """Получение статуса контейнера immich_server через SSH."""
    from .ssh_client import async_run_ssh_command
    cmd = "docker ps -a --filter \"name=immich_server\" --format \"{{.Status}}\""
    raw_status = await async_run_ssh_command(cmd, wait_for_result=True, hass=hass, entry=entry)
    if not raw_status:
        return "not_found"
    return raw_status

async def async_get_active_jobs(hass: HomeAssistant, entry: ConfigEntry) -> tuple[int, bool]:
    """Запрос фоновых задач через REST API. Возвращает (количество_задач, доступность_api)."""
    api_url = entry.data.get("immich_api_url", "").rstrip("/")
    if not api_url:
        ip = entry.data.get("server_ip", DEFAULT_SERVER_IP)
        port = entry.data.get("immich_remote_port", 2283)
        prefix = PREFIX_HTTPS if entry.data.get("immich_ssl") else PREFIX_HTTP
        api_url = f"{prefix}{ip}:{port}"

    api_key = entry.data.get("immich_api_key", "")
    full_url = f"{api_url}/api/jobs"
    headers = {"x-api-key": api_key, "Accept": "application/json"}

    try:
        session = async_get_clientsession(hass)
        async with session.get(full_url, headers=headers, timeout=5) as response:
            if response.status == 200:
                jobs_data = await response.json()
                total_active_tasks = 0
                if isinstance(jobs_data, dict):
                    for job_name, job_info in jobs_data.items():
                        if isinstance(job_info, dict):
                            counts = job_info.get("jobCounts", {})
                            if isinstance(counts, dict):
                                total_active_tasks += (counts.get("active", 0) or 0) + (counts.get("waiting", 0) or 0)
                return total_active_tasks, True
    except Exception as err:
        _LOGGER.debug(f"Не удалось связаться с API Immich по адресу {api_url} : {err}")
    return 0, False


async def async_get_local_version(hass: HomeAssistant, entry: ConfigEntry) -> str:
    """Определение локальной версии Immich строго из живого контейнера."""
    from .ssh_client import async_run_ssh_command
    
    # Пытаемся прочитать версию из запущенного Node.js окружения контейнера
    cmd = "docker exec immich_server node -e \"console.log(require('./server/package.json').version)\""
    raw_version = await async_run_ssh_command(cmd, wait_for_result=True, hass=hass, entry=entry)
    
    if raw_version and raw_version != "null" and "error" not in raw_version.lower():
        return f"v{raw_version.strip()}"
            
    # Если контейнер лежит — возвращаем пустую строку. Никаких резервных чтений .env!
    return ""
