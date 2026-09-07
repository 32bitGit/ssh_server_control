# SSH Server Control for Home Assistant

[ ! [hacs_badge] (https://img.shields.io/badge/HACS-Custom-orange.svg) ] (https://github.com/HACS/integration)
! [Version] (https://img.shields.io/badge/version-1.0.0-blue.svg)
! [License] (https://img.shields.io/badge/license-MIT-green.svg)


A powerful Home Assistant custom integration that transforms your system into a dynamic GUI constructor for managing and monitoring any Linux server over SSH using secure RSA keys.

---

## 🇷🇺 Описание на русском языке

**SSH Server Control** — это универсальная интеграция для Home Assistant, которая позволяет превратить систему в полноценный графический конструктор для управления и мониторинга любых удаленных Linux-серверов (или приставок, например Tanix W2) по протоколу SSH.

### Основные возможности (Features)
* **Мульти-хаб архитектура:** Добавляйте сколько угодно независимых Linux-серверов через стандартный интерфейс «Добавить интеграцию». Каждому серверу можно задать свое имя, IP-адрес, кастомный SSH-порт и пользователя.
* **Графический конструктор (GUI Constructor):** Нажмите на шестерёнку настроек любого добавленного сервера, чтобы на лету добавлять, редактировать или удалять кнопки и сенсоры без изменения кода Python.
* **Умные сенсоры (Dynamic Sensors):** Создавайте датчики для любых bash-команд (мониторинг ОЗУ, CPU, Docker-контейнеров, Immich). Каждому датчику можно задать свой интервал обновления в секундах и привязать единицу измерения (°C, %, МБ).
* **Многострочный редактор Jinja:** Встроенная поддержка графического редактора шаблонов Home Assistant для полей «Шаблон доступности» (Availability Template) и «Шаблон состояния» (Value Template). Обрабатывайте сырые ответы от сервера прямо в GUI.
* **Принудительный опрос (Force Update):** Все сенсоры поддерживают стандартную службу `homeassistant.update_entity`. Вы можете принудительно вызывать обновление датчиков из автоматизаций, Node-RED или API в обход таймеров.
* **Безопасность:** Подключение осуществляется строго по приватным SSH-ключам (без паролей).

---

## Installation via HACS (Установка)

1. Open **HACS** in your Home Assistant.
2. Click on the **three dots** in the top right corner and select **Custom repositories**.
3. Paste the URL of this repository into the **Repository** field.
4. Select **Integration** as the category and click **Add**.
5. Find **SSH Server Control** in the HACS search, download it, and restart Home Assistant.

## Configuration (Настройка)

1. Go to **Settings** ➔ **Devices & Services** ➔ **Add Integration**.
2. Search for **SSH Server Control**.
3. Fill in your server details:
   * **Server Name:** A custom name for your device card.
   * **IP Address:** Remote host IP or domain.
   * **SSH Port:** Custom port (defaults to 22).
   * **Username:** SSH user (e.g., `root` or `bit`).
   * **Private Key Path:** Full path to your private key (e.g., `/config/.ssh/id_rsa`).

---

## Smart Sensor Example (Пример настройки датчика ОЗУ)

To monitor free RAM on your remote machine, add a new sensor via the integration gear button with these fields:
* **Name:** `Free Memory`
* **Command:** `free -m | grep Mem | awk '{print $4}'`
* **Value template:** `{{ value | int }}`
* **Unit of measurement:** `MB`
* **Scan interval:** `30`

## License
This project is licensed under the MIT License - see the LICENSE file for details.
