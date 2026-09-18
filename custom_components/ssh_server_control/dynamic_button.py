# --- dynamic_button.py (Часть 1 из 2) ---
import logging
import asyncio
from datetime import datetime
from homeassistant.components.button import ButtonEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity import EntityCategory
from homeassistant.helpers import entity_registry as er, template as template_helper

# ТЗ: Импортируем нативный менеджер отслеживания Jinja-шаблонов ядра HA
from homeassistant.helpers.event import async_track_template_result, TrackTemplate

from .const import DOMAIN, DEFAULT_IMMICH_UPDATE_AVAIL_TEMPLATE
from .ssh_client import async_run_ssh_command

_LOGGER = logging.getLogger(__name__)

class TanixDynamicButton(ButtonEntity):
    """Класс динамической кнопки с нативным автоматическим обновлением через трекер шаблонов HA."""

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry, button_id: str, config: dict) -> None:
        """Инициализация сущности кнопки."""
        self.hass = hass
        self._entry = entry
        self._button_id = button_id
        self._config = config

        self._attr_name = config.get("name", button_id)
        self._attr_unique_id = f"ssh_srv_{entry.entry_id}_btn_{button_id}"
        self.entity_id = f"button.ssh_server_{entry.title.lower().replace(' ', '_')}_{button_id}"
        
        # Внутренняя переменная, где нативный трекер будет хранить живой булев статус доступности
        self._template_available = True

        if button_id == "immich_check_update":
            self._attr_icon = "mdi:magnify"
            self._availability_template = None
        elif button_id == "immich_run_update":
            self._attr_icon = "mdi:cellphone-arrow-down"
            self._availability_template = config.get("availability_template", DEFAULT_IMMICH_UPDATE_AVAIL_TEMPLATE)
        else:
            self._attr_icon = "mdi:remote"
            self._availability_template = config.get("availability_template", "").strip() or None

        if config.get("category") == "diagnostic":
            self._attr_entity_category = EntityCategory.DIAGNOSTIC
        else:
            self._attr_entity_category = None

        self._attr_device_info = {"identifiers": {(DOMAIN, f"server_{entry.entry_id}")}}

    @property
    def should_poll(self) -> bool:
        """Поллинг отключен, кнопка реактивно обновляется нативными событиями шаблона."""
        return False

    @property
    def available(self) -> bool:
        """Возвращает статус доступности, который ядро HA само обновляет в памяти."""
        if not self._availability_template:
            return True
        return self._template_available
# --- dynamic_button.py (Часть 2 из 2) ---


    async def async_added_to_hass(self) -> None:
        """Вызывается при добавлении кнопки в HA. Регистрируем нативный трекер шаблона."""
        if not self._availability_template:
            return

        ent_reg = er.async_get(self.hass)
        up_sid = ent_reg.async_get_entity_id("sensor", DOMAIN, f"ssh_srv_{self._entry.entry_id}_snr_immich_update")
        if not up_sid:
            up_sid = f"sensor.ssh_server_{self._entry.title.lower().replace(' ', '_')}_immich_update"

        @callback
        def _async_template_result_listener(event, updates):
            """Автоматический коллбек ядра HA: срабатывает, когда сущности внутри Jinja меняют стейт."""
            result = updates.pop().result
            
            if isinstance(result, str):
                self._template_available = result.strip().lower() == "true"
            else:
                self._template_available = bool(result)
                
            _LOGGER.debug(f"🔘 [НАТИВНЫЙ ТРЕКЕР КНОПКИ] Шаблон пересчитан ядром HA: {self._template_available}")
            self.async_write_ha_state()

        # ТЗ: Заменяем ошибочный async_on_unload на корректный async_on_remove для сущностей HA
        self.async_on_remove(
            async_track_template_result(
                self.hass,
                [TrackTemplate(template_helper.Template(self._availability_template, self.hass), {"entity_id": self.entity_id, "up_entity_id": up_sid})],
                _async_template_result_listener,
            )
        )


    async def async_press(self) -> None:
        """Срабатывает при нажатии на кнопку в GUI."""
        command = self._config.get("command", "").strip()
        if not command:
            return

        if command == "__api_immich_force_check_update__":
            ent_reg = er.async_get(self.hass)
            sensor_id = ent_reg.async_get_entity_id("sensor", DOMAIN, f"ssh_srv_{self._entry.entry_id}_snr_immich_update")
            if sensor_id:
                from homeassistant.helpers.entity_component import async_update_entity
                await async_update_entity(self.hass, sensor_id)
            return

        if command == "__api_immich_run_update_sequence__":
            _LOGGER.info("Запуск фоновой цепочки обновления Immich...")
            self.hass.async_create_task(self._async_execute_update_sequence())
            return

        wait_for_result = self._config.get("wait_for_result", True)
        await async_run_ssh_command(command, wait_for_result=wait_for_result, hass=self.hass, entry=self._entry)

    async def _async_execute_update_sequence(self) -> None:
        """Боевая цепочка обновлений Immich, оптимизированная под ограничения производительности железа."""
        entry_id = self._entry.entry_id
        compose_path = self._entry.data.get("immich_compose_path", "")
        backup_path = self._entry.data.get("immich_backup_path", "").rstrip("/")
        db_user = self._entry.data.get("immich_db_user", "postgres")
        
        keep_days = self._entry.options.get("immich_backup_keep_days", 14)
        keep_count = self._entry.options.get("immich_backup_keep_count", 5)
        base_dir = compose_path.replace("docker-compose.yml", "").replace("docker-compose.yaml", "").rstrip("/")

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_file = f"{backup_path}/immich_backup_{timestamp}.sql"

        ent_reg = er.async_get(self.hass)
        status_sid = ent_reg.async_get_entity_id("sensor", DOMAIN, f"ssh_srv_{entry_id}_snr_immich_status")
        update_sid = ent_reg.async_get_entity_id("sensor", DOMAIN, f"ssh_srv_{entry_id}_snr_immich_update")

        if not status_sid or not update_sid:
            _LOGGER.error("Не удалось найти целевые сенсоры Immich для запуска обновления.")
            return

        from homeassistant.helpers.entity_component import async_update_entity

        try:
            # Шаг 1: Комплексная предпроверка состояния систем перед стартом
            _LOGGER.info("Кнопка run запрашивает комплексную предпроверку состояния систем...")
            await async_update_entity(self.hass, status_sid)
            await async_update_entity(self.hass, update_sid)

            status_state = self.hass.states.get(status_sid)
            update_state = self.hass.states.get(update_sid)

            if not status_state or not update_state:
                raise Exception("Не удалось получить текущие состояния датчиков из памяти HA.")

            container_ok = status_state.attributes.get("container_is_running", False)
            api_ok = status_state.attributes.get("api_is_online", False)
            is_busy = status_state.state in ["busy", "Занят (Обработка файлов)"]
            has_update = update_state.attributes.get("update_available", False)
            is_breaking = update_state.attributes.get("breaking_changes", False)
            
            force_sid = update_state.attributes.get("force_mode_entity_id")
            force_on = self.hass.states.is_state(force_sid, "on") if force_sid else False

            if not container_ok or not api_ok:
                raise Exception("Прерывание: контейнер Immich или его API недоступны.")
            if is_busy:
                raise Exception("Прерывание: сервер Immich сейчас занят выполнением фоновых задач!")
            if not has_update:
                raise Exception("Прерывание: нет доступных обновлений для установки.")
            if is_breaking and not force_on:
                raise Exception("Прерывание: обнаружено критическое обновление, но защитный тумблер выключен!")

            # Шаг 2: Создание резервной копии базы данных PostgreSQL
            _LOGGER.info("Старт создания резервной копии базы данных PostgreSQL...")
            self.hass.data[DOMAIN][f"updating_status_{entry_id}"] = "backup"
            self.hass.states.async_set(status_sid, "backup")
            
            await async_run_ssh_command(f"mkdir -p {backup_path}", hass=self.hass, entry=self._entry)
            backup_cmd = f"docker exec -i immich_postgres pg_dumpall -c -U {db_user} > {backup_file}"
            await async_run_ssh_command(backup_cmd, hass=self.hass, entry=self._entry)
            
            check_size = await async_run_ssh_command(f"[ -s {backup_file} ] && echo 'OK' || echo 'EMPTY'", hass=self.hass, entry=self._entry)
            if "OK" not in check_size:
                raise Exception("Созданный ... файл бэкапа базы данных пуст или не записался на диск!")

            # Шаг 3: Скачивание свежих Docker-слоев с жесткой проверкой целостности по оператору &&
            _LOGGER.info("Бэкап создан и проверен. Скачиваем новые образы через docker compose pull...")
            self.hass.data[DOMAIN][f"updating_status_{entry_id}"] = "pulling"
            self.hass.states.async_set(status_sid, "pulling")
            
            # Если скачивание прервется, строка PULL_SUCCESS не будет выведена, и сработает исключение
            pull_result = await async_run_ssh_command(
                f"cd {base_dir} && docker compose pull && echo 'PULL_SUCCESS'", 
                hass=self.hass, 
                entry=self._entry
            )
            
            if "PULL_SUCCESS" not in pull_result:
                raise Exception("Скачивание Docker-образов завершилось ошибкой или прервалось по таймауту сети!")

            
            # ТЗ: Передаем ручной таймаут 300 сек прямо в функцию SSH-клиента, если она это поддерживает,
            # либо полагаемся на глобальное расширение таймаута в ssh_client.py
            await async_run_ssh_command(f"cd {base_dir} && docker compose pull", hass=self.hass, entry=self._entry)

            # Шаг 4: Перезапуск и принудительное применение новой версии контейнеров
            _LOGGER.info("Образы скачаны. Применяем обновление и принудительно пересоздаем контейнеры...")
            self.hass.data[DOMAIN][f"updating_status_{entry_id}"] = "restarting"
            self.hass.states.async_set(status_sid, "restarting")
            
            # Флаг --force-recreate гарантирует, что Docker не проигнорирует запуск апдейта
            await async_run_ssh_command(f"cd {base_dir} && docker compose up -d --force-recreate", hass=self.hass, entry=self._entry)

            # Шаг 5: Очистка старых зависших слоев Docker
            self.hass.data[DOMAIN][f"updating_status_{entry_id}"] = "pruning"
            self.hass.states.async_set(status_sid, "pruning")
            await async_run_ssh_command("docker image prune -f", hass=self.hass, entry=self._entry)

            # Шаг 6: Поштучная ротация архивов (Вызывается только при 100% успехе цепочки)
            _LOGGER.info("Запуск ротации бэкапов по количеству...")
            await async_run_ssh_command(f"find {backup_path} -name \"immich_backup_*.sql\" -mtime +{keep_days} -delete", hass=self.hass, entry=self._entry)
            cleanup_count_cmd = f"cd {backup_path} && ls -tp immich_backup_*.sql | grep -v '/$' | tail -n +{keep_count + 1} | xargs -I {{}} rm -- {{}}"
            await async_run_ssh_command(cleanup_count_cmd, hass=self.hass, entry=self._entry)

            # Шаг 7: Вывод надписи успеха на 15 секунд
            self.hass.data[DOMAIN][f"updating_status_{entry_id}"] = "success"
            self.hass.states.async_set(status_sid, "success")
            await asyncio.sleep(15)

        except Exception as err:
            _LOGGER.error(f"Критическая ошибка во время цепочки обновления Immich: {err}")
            self.hass.data[DOMAIN][f"updating_status_{entry_id}"] = "error"
            self.hass.states.async_set(status_sid, "error")
            await asyncio.sleep(15)

        # Финал: Даем СУБД и контейнерам 10 секунд спокойно завершить миграции перед финальным опросом датчиков
        _LOGGER.info("Ожидаем стабилизации процессора приставки после перезапуска Docker...")
        await asyncio.sleep(10)
        
        self.hass.data[DOMAIN][f"updating_status_{entry_id}"] = ""
        await async_update_entity(self.hass, status_sid)
        await async_update_entity(self.hass, update_sid)
        _LOGGER.info("Боевая цепочка обновления полностью завершена.")
