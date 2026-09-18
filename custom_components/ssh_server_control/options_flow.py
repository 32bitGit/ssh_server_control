import copy
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.data_entry_flow import FlowResult
from homeassistant.util import slugify
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.translation import async_get_cached_translations
from homeassistant.helpers.selector import (
    TemplateSelector,
    SelectSelector,
    SelectSelectorConfig,
    SelectSelectorMode
)

from .const import (
    DOMAIN, 
    DEFAULT_IMMICH_UPDATE_AVAIL_TEMPLATE,
    DEFAULT_IMMICH_UPDATE_VALUE_TEMPLATE
)

class SSHServerControlOptionsFlowHandler(config_entries.OptionsFlow):
    """Главный конструктор и меню изменения параметров хаба (Options Flow)."""

    def __init__(self, config_entry: config_entries.ConfigEntry) -> None:
        """Инициализация."""
        self._config_entry = config_entry
        self._editing_type = None
        self._editing_id = None

    async def async_step_init(self, user_input=None) -> FlowResult:
        """Шаг 1: Главное меню действий в шестеренке."""
        options = self._config_entry.options
        has_objects = bool(options.get("buttons") or options.get("sensors") or options.get("switches"))
        hub_type = self._config_entry.data.get("hub_type", "generic")

        menu_options = []
        if hub_type == "immich":
            menu_options.append("immich_settings")

        menu_options.extend(["add_button", "add_sensor"])

        if has_objects or hub_type == "immich":
            menu_options.append("manage_menu")

        return self.async_show_menu(step_id="init", menu_options=menu_options)

    async def async_step_immich_settings(self, user_input=None) -> FlowResult:
        """Форма параметров резервного копирования Immich."""
        current_options = copy.deepcopy(dict(self._config_entry.options))

        if user_input is not None:
            current_options.update(user_input)
            return self.async_create_entry(title="", data=current_options)

        return self.async_show_form(
            step_id="immich_settings",
            data_schema=vol.Schema({
                vol.Required("immich_backup_keep_days", default=current_options.get("immich_backup_keep_days", 14)): int,
                vol.Required("immich_backup_keep_count", default=current_options.get("immich_backup_keep_count", 5)): int,
            })
        )

    async def _async_get_entity_display_name(self, platform: str, entity_uid: str, fallback_name: str, label_key: str) -> str:
        """Вспомогательный метод для получения актуального имени из реестра HA с локализацией типа."""
        ent_reg = er.async_get(self.hass)
        full_uid = f"ssh_srv_{self._config_entry.entry_id}_{entity_uid}"
        entity_id = ent_reg.async_get_entity_id(platform, DOMAIN, full_uid)
        
        display_name = fallback_name
        if entity_id:
            entity_entry = ent_reg.async_get(entity_id)
            if entity_entry:
                display_name = entity_entry.name or entity_entry.original_name or fallback_name

        # Запрашиваем кэш переводов именно для раздела параметров (options)
        translations = async_get_cached_translations(self.hass, self.hass.config.language, "options", DOMAIN)
        
        # Строим системный путь к строке перевода внутри структуры шага manage_menu
        exact_key = f"component.{DOMAIN}.options.step.manage_menu.management.{label_key}"
        template_str = translations.get(exact_key)
        
        # Если кэш HA еще не обновился в памяти, используем стабильный фоллбек-формат
        if not template_str:
            prefix_fallback = label_key.replace("builtin_", "Встроенный ").replace("custom_", "").capitalize()
            template_str = f"[{prefix_fallback}] {{name}}"
            
        return template_str.format(name=display_name)


    async def async_step_manage_menu(self, user_input=None) -> FlowResult:
        """Выпадающий список доступных объектов с именами из реестра HA."""
        if user_input is not None:
            target = user_input.get("target_object")
            if target:
                obj_type, obj_id = target.split(":", 1)
                self._editing_type = obj_type
                self._editing_id = obj_id
                return await self.async_step_manage_object()

        options = self._config_entry.options
        hub_type = self._config_entry.data.get("hub_type", "generic")
        select_options = []
        
        # 1. Встроенные кнопки и тумблеры Immich
        if hub_type == "immich":
            name_check = await self._async_get_entity_display_name("button", "btn_immich_check_update", "Immich Check Update", "builtin_button")
            select_options.append({"value": "button:immich_check_update", "label": name_check})
            
            name_run = await self._async_get_entity_display_name("button", "btn_immich_run_update", "Immich Run Update", "builtin_button")
            select_options.append({"value": "button:immich_run_update", "label": name_run})
            
            name_force = await self._async_get_entity_display_name("switch", "immich_force_mode", "Immich Force Mode", "builtin_switch")
            select_options.append({"value": "switch:immich_force_mode", "label": name_force})

        # 2. Пользовательские кнопки
        for b_id, b_data in options.get("buttons", {}).items():
            if b_id in ["immich_check_update", "immich_run_update"]:
                continue
            name_custom_btn = await self._async_get_entity_display_name("button", f"btn_{b_id}", b_data.get("name", b_id), "custom_button")
            select_options.append({"value": f"button:{b_id}", "label": name_custom_btn})

        # 3. Встроенные датчики Immich
        if hub_type == "immich":
            name_status = await self._async_get_entity_display_name("sensor", "snr_immich_status", "Immich Status", "builtin_sensor")
            select_options.append({"value": "sensor:immich_status", "label": name_status})
            
            name_update = await self._async_get_entity_display_name("sensor", "snr_immich_update", "Immich Update", "builtin_sensor")
            select_options.append({"value": "sensor:immich_update", "label": name_update})
            
            name_last = await self._async_get_entity_display_name("sensor", "snr_immich_last_check", "Immich Last Check", "builtin_sensor")
            select_options.append({"value": "sensor:immich_last_check", "label": name_last})

        # 4. Остальные кастомные датчики
        for s_id, s_data in options.get("sensors", {}).items():
            if s_id in ["immich_status", "immich_update", "immich_last_check"]:
                continue
            name_custom_snr = await self._async_get_entity_display_name("sensor", f"snr_{s_id}", s_data.get("name", s_id), "custom_sensor")
            select_options.append({"value": f"sensor:{s_id}", "label": name_custom_snr})

        return self.async_show_form(
            step_id="manage_menu", 
            data_schema=vol.Schema({
                vol.Required("target_object"): SelectSelector(
                    SelectSelectorConfig(options=select_options, mode=SelectSelectorMode.DROPDOWN)
                )
            })
        )

    async def async_step_manage_object(self, user_input=None) -> FlowResult:
        """Операция над объектом: безопасное удаление или переход к редактированию."""
        current_options = copy.deepcopy(dict(self._config_entry.options))
        dict_key = f"{self._editing_type}s"

        # Защита встроенных сущностей от случайного удаления из базы HA
        protected_ids = [
            "immich_status", 
            "immich_update", 
            "immich_last_check", 
            "immich_check_update", 
            "immich_run_update", 
            "immich_force_mode"
        ]
        is_protected = self._editing_id in protected_ids

        if user_input is not None:
            if user_input.get("delete_object") and not is_protected:
                if dict_key in current_options and self._editing_id in current_options[dict_key]:
                    del current_options[dict_key][self._editing_id]
                return self.async_create_entry(title="", data=current_options)
            
            if self._editing_type == "button":
                return await self.async_step_add_button()
            elif self._editing_type == "switch":
                return await self.async_step_add_switch()
            else:
                return await self.async_step_add_sensor()

        if is_protected:
            if self._editing_type == "button":
                return await self.async_step_add_button()
            elif self._editing_type == "switch":
                return await self.async_step_add_switch()
            else:
                return await self.async_step_add_sensor()

        return self.async_show_form(
            step_id="manage_object",
            data_schema=vol.Schema({
                vol.Required("delete_object", default=False): bool
            })
        )

    async def async_step_add_button(self, user_input=None) -> FlowResult:
        """Форма настройки и редактирования кнопок."""
        errors = {}
        current_options = copy.deepcopy(dict(self._config_entry.options))
        buttons_dict = current_options.get("buttons", {})

        if self._editing_id == "immich_check_update":
            defaults = {
                "name": "Immich Check Update", 
                "command": "__api_immich_force_check_update__", 
                "availability_template": "", 
                "wait_for_result": False, 
                "category": "main"
            }
        elif self._editing_id == "immich_run_update":
            defaults = {
                "name": "Immich Run Update", 
                "command": "__api_immich_run_update_sequence__", 
                "availability_template": DEFAULT_IMMICH_UPDATE_AVAIL_TEMPLATE, 
                "wait_for_result": False, 
                "category": "main"
            }
        else:
            defaults = {
                "name": "", 
                "command": "", 
                "availability_template": "", 
                "wait_for_result": True, 
                "category": "main"
            }

        if self._editing_id and self._editing_id in buttons_dict:
            defaults.update(buttons_dict[self._editing_id])

        if user_input is not None:
            button_id = self._editing_id if self._editing_id else slugify(user_input["name"])

            if "buttons" not in current_options:
                current_options["buttons"] = {}

            if not self._editing_id and button_id in current_options["buttons"]:
                errors["base"] = "button_already_exists"
            else:
                current_options["buttons"][button_id] = {
                    "name": user_input["name"],
                    "command": defaults["command"] if self._editing_id in ["immich_check_update", "immich_run_update"] else user_input["command"],
                    "availability_template": user_input.get("availability_template", ""),
                    "wait_for_result": user_input["wait_for_result"],
                    "category": user_input["category"],
                }
                return self.async_create_entry(title="", data=current_options)

        schema_fields = {
            vol.Required("name", default=defaults["name"]): str,
        }

        if self._editing_id not in ["immich_check_update", "immich_run_update"]:
            schema_fields[vol.Required("command", default=defaults["command"])] = str

        schema_fields.update({
            vol.Optional("availability_template", default=defaults["availability_template"]): TemplateSelector(),
            vol.Required("wait_for_result", default=defaults["wait_for_result"]): bool,
            vol.Required("category", default=defaults["category"]): SelectSelector(
                SelectSelectorConfig(
                    options=[
                        {"value": "main", "label": "main"},
                        {"value": "diagnostic", "label": "diagnostic"}
                    ],
                    mode=SelectSelectorMode.DROPDOWN,
                    translation_key="category"
                )
            ),
        })

        return self.async_show_form(
            step_id="add_button",
            data_schema=vol.Schema(schema_fields),
            errors=errors
        )
    async def async_step_add_switch(self, user_input=None) -> FlowResult:
        """Форма настройки встроенного или кастомного тумблера."""
        errors = {}
        current_options = copy.deepcopy(dict(self._config_entry.options))
        switches_dict = current_options.get("switches", {})

        if self._editing_id == "immich_force_mode":
            defaults = {"name": "Immich Force Mode", "availability_template": "", "category": "diagnostic"}
        else:
            defaults = {"name": "", "availability_template": "", "category": "main"}

        if self._editing_id and self._editing_id in switches_dict:
            defaults.update(switches_dict[self._editing_id])

        if user_input is not None:
            if "switches" not in current_options:
                current_options["switches"] = {}

            current_options["switches"][self._editing_id] = {
                "name": user_input["name"],
                "availability_template": user_input.get("availability_template", ""),
                "category": user_input["category"]
            }
            return self.async_create_entry(title="", data=current_options)

        return self.async_show_form(
            step_id="add_switch",
            data_schema=vol.Schema({
                vol.Required("name", default=defaults["name"]): str,
                vol.Optional("availability_template", default=defaults["availability_template"]): TemplateSelector(),
                vol.Required("category", default=defaults["category"]): SelectSelector(
                    SelectSelectorConfig(
                        options=[
                            {"value": "main", "label": "main"},
                            {"value": "diagnostic", "label": "diagnostic"}
                        ],
                        mode=SelectSelectorMode.DROPDOWN,
                        translation_key="category"
                    )
                ),
            }),
            errors=errors
        )

    async def async_step_add_sensor(self, user_input=None) -> FlowResult:
        """Форма настройки и изменения параметров датчика."""
        errors = {}
        current_options = copy.deepcopy(dict(self._config_entry.options))
        sensors_dict = current_options.get("sensors", {})

        if self._editing_id == "immich_status":
            defaults = {"name": "Immich Status", "command": "__api_immich_status__", "availability_template": "", "value_template": "", "unit_of_measurement": "", "scan_interval": 1200, "category": "main"}
        elif self._editing_id == "immich_update":
            defaults = {"name": "Immich Update", "command": "__api_immich_update__", "availability_template": "", "value_template": DEFAULT_IMMICH_UPDATE_VALUE_TEMPLATE, "unit_of_measurement": "", "scan_interval": 86400, "category": "main"}
        elif self._editing_id == "immich_last_check":
            defaults = {"name": "Immich Last Check", "command": "", "availability_template": "", "value_template": "{{ state_attr(up_entity_id, 'last_check_time') }}", "unit_of_measurement": "", "scan_interval": 0, "category": "diagnostic"}
        else:
            defaults = {"name": "", "command": "", "availability_template": "", "value_template": "", "unit_of_measurement": "", "scan_interval": 30, "category": "main"}

        if self._editing_id and self._editing_id in sensors_dict:
            defaults.update(sensors_dict[self._editing_id])

        if user_input is not None:
            sensor_id = self._editing_id if self._editing_id else slugify(user_input["name"])

            if "sensors" not in current_options:
                current_options["sensors"] = {}

            if not self._editing_id and sensor_id in current_options["sensors"]:
                errors["base"] = "sensor_already_exists"
            else:
                final_command = defaults["command"] if self._editing_id in ["immich_status", "immich_update", "immich_last_check"] else user_input["command"]
                
                current_options["sensors"][sensor_id] = {
                    "name": user_input["name"],
                    "command": final_command,
                    "availability_template": user_input.get("availability_template", ""),
                    "value_template": user_input.get("value_template", ""),
                    "unit_of_measurement": user_input.get("unit_of_measurement", ""),
                    "scan_interval": int(user_input["scan_interval"]),
                    "category": user_input["category"],
                }
                return self.async_create_entry(title="", data=current_options)

        schema_fields = {
            vol.Required("name", default=defaults["name"]): str,
        }
        
        if self._editing_id not in ["immich_status", "immich_update", "immich_last_check"]:
            schema_fields[vol.Required("command", default=defaults["command"])] = str

        schema_fields.update({
            vol.Optional("value_template", default=defaults["value_template"]): TemplateSelector(),
            vol.Optional("unit_of_measurement", default=defaults["unit_of_measurement"]): str,
            vol.Optional("availability_template", default=defaults["availability_template"]): TemplateSelector(),
            vol.Required("scan_interval", default=defaults["scan_interval"]): int,
            vol.Required("category", default=defaults["category"]): SelectSelector(
                SelectSelectorConfig(
                    options=[
                        {"value": "main", "label": "main"},
                        {"value": "diagnostic", "label": "diagnostic"}
                    ],
                    mode=SelectSelectorMode.DROPDOWN,
                    translation_key="category"
                )
            ),
        })

        return self.async_show_form(
            step_id="add_sensor",
            data_schema=vol.Schema(schema_fields),
            errors=errors
        )
