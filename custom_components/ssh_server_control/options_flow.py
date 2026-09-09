import voluptuous as vol
from homeassistant import config_entries
from homeassistant.data_entry_flow import FlowResult
from homeassistant.helpers.selector import TemplateSelector

class SshServerControlOptionsFlowHandler(config_entries.OptionsFlow):
    """Главный хаб-конструктор объектов сервера (Options Flow)."""

    def __init__(self, config_entry: config_entries.ConfigEntry) -> None:
        """Инициализация."""
        self._config_entry = config_entry
        self._editing_type = None
        self._editing_id = None

    async def async_step_init(self, user_input=None) -> FlowResult:
        """Шаг 1: Главное меню действий."""
        options = self._config_entry.options
        has_objects = bool(options.get("buttons") or options.get("sensors"))

        menu_options = {
            "add_button": "Добавить новую кнопку",
            "add_sensor": "Добавить новый сенсор",
        }

        if has_objects:
            menu_options["manage_menu"] = "Редактировать или удалить объект"

        return self.async_show_menu(step_id="init", menu_options=menu_options)

    async def async_step_manage_menu(self, user_input=None) -> FlowResult:
        """Шаг 2: Выпадающий список созданных объектов."""
        if user_input is not None:
            target = user_input.get("target_object")
            if target:
                obj_type, obj_id = target.split(":", 1)
                self._editing_type = obj_type
                self._editing_id = obj_id
                return await self.async_step_manage_object()

        options = self._config_entry.options
        existing_buttons = options.get("buttons", {})
        existing_sensors = options.get("sensors", {})

        dropdown_items = {}
        for b_id, b_data in existing_buttons.items():
            dropdown_items[f"button:{b_id}"] = f"Кнопка: {b_data.get('name')} [{b_id}]"
            
        for s_id, s_data in existing_sensors.items():
            dropdown_items[f"sensor:{s_id}"] = f"Сенсор: {s_data.get('name')} [{s_id}]"

        schema = vol.Schema({
            vol.Required("target_object"): vol.In(dropdown_items)
        })

        return self.async_show_form(step_id="manage_menu", data_schema=schema)

    async def async_step_manage_object(self, user_input=None) -> FlowResult:
        """Шаг 3: Выбор действия над объектом."""
        if user_input is not None:
            action = user_input.get("object_action")
            current_options = dict(self._config_entry.options)
            dict_key = "buttons" if self._editing_type == "button" else "sensors"

            if action == "delete":
                if dict_key in current_options and self._editing_id in current_options[dict_key]:
                    del current_options[dict_key][self._editing_id]
                return self.async_create_entry(title="", data=current_options)
                
            elif action == "edit":
                if self._editing_type == "button":
                    return await self.async_step_add_button()
                else:
                    return await self.async_step_add_sensor()

        return self.async_show_form(
            step_id="manage_object",
            data_schema=vol.Schema({
                vol.Required("object_action", default="edit"): vol.In({
                    "edit": "Редактировать настройки",
                    "delete": "Полностью удалить объект"
                })
            })
        )

    async def async_step_add_button(self, user_input=None) -> FlowResult:
        """Форма параметров кнопки."""
        errors = {}
        current_options = dict(self._config_entry.options)
        buttons_dict = current_options.get("buttons", {})

        defaults = {"name": "", "command": "", "availability_template": "", "wait_for_result": True}
        if self._editing_id and self._editing_id in buttons_dict:
            defaults = buttons_dict[self._editing_id]

        if user_input is not None:
            from homeassistant.util import slugify
            button_id = self._editing_id if self._editing_id else slugify(user_input["name"])

            if "buttons" not in current_options:
                current_options["buttons"] = {}

            if not self._editing_id and button_id in current_options["buttons"]:
                errors["base"] = "button_already_exists"
            else:
                current_options["buttons"][button_id] = {
                    "name": user_input["name"],
                    "command": user_input["command"],
                    "availability_template": user_input.get("availability_template", ""),
                    "wait_for_result": user_input["wait_for_result"],
                }
                return self.async_create_entry(title="", data=current_options)

        button_schema = vol.Schema(
            {
                vol.Required("name", default=defaults["name"]): str,
                vol.Required("command", default=defaults["command"]): str,
                vol.Optional("availability_template", default=defaults["availability_template"]): TemplateSelector(),
                vol.Required("wait_for_result", default=defaults["wait_for_result"]): bool,
            }
        )
        return self.async_show_form(step_id="add_button", data_schema=button_schema, errors=errors)

    async def async_step_add_sensor(self, user_input=None) -> FlowResult:
        """Форма параметров сенсора."""
        errors = {}
        current_options = dict(self._config_entry.options)
        sensors_dict = current_options.get("sensors", {})

        defaults = {"name": "", "command": "", "availability_template": "", "value_template": "", "unit_of_measurement": "", "scan_interval": 30, "category": "main"}
        if self._editing_id and self._editing_id in sensors_dict:
            defaults = sensors_dict[self._editing_id]

        if user_input is not None:
            from homeassistant.util import slugify
            sensor_id = self._editing_id if self._editing_id else slugify(user_input["name"])

            if "sensors" not in current_options:
                current_options["sensors"] = {}

            if not self._editing_id and sensor_id in current_options["sensors"]:
                errors["base"] = "sensor_already_exists"
            else:
                current_options["sensors"][sensor_id] = {
                    "name": user_input["name"],
                    "command": user_input["command"],
                    "availability_template": user_input.get("availability_template", ""),
                    "value_template": user_input.get("value_template", ""),
                    "unit_of_measurement": user_input.get("unit_of_measurement", ""),
                    "scan_interval": int(user_input["scan_interval"]),
                    "category": user_input["category"],
                }
                return self.async_create_entry(title="", data=current_options)

        categories_list = {"main": "Основной сенсор", "diagnostic": "Диагностика"}
        sensor_schema = vol.Schema(
            {
                vol.Required("name", default=defaults["name"]): str,
                vol.Required("command", default=defaults["command"]): str,
                vol.Optional("value_template", default=defaults["value_template"]): TemplateSelector(),
                vol.Optional("unit_of_measurement", default=defaults["unit_of_measurement"]): str,
                vol.Optional("availability_template", default=defaults["availability_template"]): TemplateSelector(),
                vol.Required("scan_interval", default=defaults["scan_interval"]): int,
                vol.Required("category", default=defaults["category"]): vol.In(categories_list),
            }
        )
        return self.async_show_form(step_id="add_sensor", data_schema=sensor_schema, errors=errors)
