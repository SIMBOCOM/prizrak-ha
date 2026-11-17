# Prizrak Monitoring без GPS для Home Assistant

<img src="custom_components/prizrak/brand/icon.png" width="72" height="72" alt="Значок приложения Призрак 2.0">

Интеграция для системы мониторинга автомобилей Prizrak (monitoring.tecel.ru). Эта версия сохраняет телеметрию, охрану и управление автомобилем, а GPS-данные отбрасывает.

## Возможности

- **Обновления в реальном времени** через WebSocket соединение
- **Датчики автомобиля**
  - Телеметрия (напряжение батареи, уровень топлива, температуры, обороты, одометр)
  - Безопасность (статус охраны, сигнализация)
  - GSM сигнал и баланс SIM-карты
  - Системы обогрева (сидения, стекла, зеркала, руль)
- **Бинарные сенсоры** для дверей, багажника, капота и замков
- **Кнопки управления** для охраны и автозапуска
- **Автоматическое переподключение** с мониторингом состояния соединения

## Установка

### Через HACS

1. Откройте HACS → ⋮ → «Пользовательские репозитории».
2. Вставьте `https://github.com/SIMBOCOM/prizrak-ha`, выберите тип **Integration** («Интеграция») и нажмите «Добавить».
3. Откройте **Prizrak Monitoring без GPS**, нажмите «Скачать» и перезапустите Home Assistant.
4. При первой установке добавьте **Prizrak Monitoring** в разделе «Настройки → Устройства и службы». Если интеграция уже настроена, она использует существующую запись.

Эта версия использует тот же домен `prizrak`, что и исходный проект. Если Marketplace сообщает `The prizrak directory belongs to dsultanr/prizrak-ha-integration`, воспользуйтесь инструкцией по [переходу с исходной интеграции](INSTALLATION.md#switch-repository).

### Ручная установка

1. Скопируйте директорию `custom_components/prizrak` в директорию `custom_components` вашего Home Assistant
2. Перезапустите Home Assistant

## Настройка

1. Перейдите в **Настройки** → **Устройства и службы**
2. Нажмите **"+ ДОБАВИТЬ ИНТЕГРАЦИЮ"**
3. Найдите **"Prizrak Monitoring"**
4. Введите ваш **email и пароль от monitoring.tecel.ru**
5. Нажмите **Отправить**

Ваши устройства Prizrak появятся автоматически со всеми доступными сенсорами!

## Использование

### Страница устройства

После настройки все сенсоры и кнопки управления автоматически группируются на странице устройства:

1. Перейдите в **Настройки** → **Устройства и службы** → **Prizrak Monitoring**
2. Нажмите на ваше устройство (например, "Кодиак")
3. Вы увидите все сенсоры, кнопки и бинарные сенсоры

Home Assistant автоматически предложит добавить устройство в зону **"Garage"**.

### Добавление на Dashboard

Вы можете добавить entities на ваш dashboard несколькими способами:

**Вариант 1: Через GUI (рекомендуется)**
1. Откройте ваш Dashboard
2. Нажмите **"Редактировать"** (три точки справа вверху)
3. Нажмите **"+ Добавить карточку"**
4. Выберите карточку (например, "Entities" или "Picture Elements")
5. Добавьте нужные entities из списка

**Вариант 2: YAML конфигурация**

Пример карточки для dashboard:

```yaml
type: vertical-stack
cards:
  - type: entities
    title: Статус автомобиля
    entities:
      - entity: binary_sensor.prizrak_95311_connection
      - entity: binary_sensor.prizrak_95311_guard
      - entity: binary_sensor.prizrak_95311_alarm
      - entity: binary_sensor.prizrak_95311_ignition
      - entity: sensor.prizrak_95311_battery_voltage
      - entity: sensor.prizrak_95311_gsm_level
      - entity: sensor.prizrak_95311_last_update

  - type: horizontal-stack
    cards:
      - type: button
        name: Охрана Вкл
        entity: button.prizrak_95311_guard_on
        icon: mdi:shield-check
        tap_action:
          action: call-service
          service: button.press
          target:
            entity_id: button.prizrak_95311_guard_on
      - type: button
        name: Охрана Выкл
        entity: button.prizrak_95311_guard_off
        icon: mdi:shield-off
        tap_action:
          action: call-service
          service: button.press
          target:
            entity_id: button.prizrak_95311_guard_off

  - type: entities
    title: Двери и замки
    entities:
      - entity: binary_sensor.prizrak_95311_driver_door
      - entity: binary_sensor.prizrak_95311_front_pass_door
      - entity: binary_sensor.prizrak_95311_rear_left_door
      - entity: binary_sensor.prizrak_95311_rear_right_door
      - entity: binary_sensor.prizrak_95311_trunk
      - entity: binary_sensor.prizrak_95311_hood
      - entity: binary_sensor.prizrak_95311_central_lock

  - type: entities
    title: Телеметрия
    entities:
      - entity: sensor.prizrak_95311_speed
      - entity: sensor.prizrak_95311_rpm
      - entity: sensor.prizrak_95311_odometer
      - entity: sensor.prizrak_95311_fuel_level
      - entity: sensor.prizrak_95311_temperature
      - entity: sensor.prizrak_95311_engine_temperature

```

**Примечание:** Замените `95311` на ID вашего устройства (он указан в entity_id).

## Визуализация автомобиля

Интеграция включает готовую **интерактивную карточку автомобиля** с динамической визуализацией:

### Автоматическая установка ресурсов

При первом запуске интеграции автоматически устанавливаются все необходимые файлы в `/config/www/prizrak/`.

### Функции карточки

**Динамическая визуализация:**
- 🔵 **Guard ON**: Голубое свечение вокруг машины + закрытый замок
- ⚪ **Guard OFF**: Серый контур + открытый замок
- 🚗 **Autolaunch ON**: Белый контур + светящиеся фары и стоп-сигналы + иконка двигателя
- 🟡 **Открытые двери**: Желтая подсветка каждой двери (водительская, пассажирская, задние, капот, багажник)

**Отображаемая информация:**
- Напряжение батареи
- Температура двигателя
- Уровень топлива
- Температура снаружи/в салоне
- Скорость и обороты (при автозапуске)

### Установка карточки

1. Откройте Dashboard → Редактировать
2. Добавить карточку → Вручную (Manual)
3. Скопируйте содержимое из `examples/car-card.yaml` (в репозитории интеграции)
4. Замените `95311` на ID вашего устройства
5. Сохраните

Пример карточки: [examples/car-card.yaml](examples/car-card.yaml)

## Сенсоры

### Бинарные сенсоры (Binary Sensors)

**Безопасность:**
- 🔌 Подключение (Connection)
- 🛡️ Охрана (Guard)
- 🚨 Тревога (Alarm)

При обрыве облачного соединения или сообщении автомобиля о потере связи оба датчика переходят в состояние «Недоступно». Если от отдельного автомобиля перестают поступать обновления, интеграция обнаруживает это по тайм-ауту в 120 секунд с проверкой каждые 10 секунд. При восстановлении связи каждый датчик ждёт своего первого свежего значения.

**Двери и замки:**
- 🚗 Водительская дверь
- 🚗 Пассажирская дверь
- 🚗 Задняя левая дверь
- 🚗 Задняя правая дверь
- 🚗 Багажник
- 🚗 Капот
- 🔒 Центральный замок

**Двигатель и системы:**
- 🔑 Зажигание (Ignition)
- 🅿️ Ручной тормоз (Parking Brake)

### Обычные сенсоры (Sensors)

**Телеметрия автомобиля:**
- Напряжение батареи
- Уровень топлива
- Температура в салоне
- Температура снаружи
- Температура двигателя
- Скорость
- Обороты двигателя
- Одометр

**Связь:**
- Уровень GSM сигнала
- Оператор SIM-карты
- Баланс SIM-карты

**Системы обогрева:**
- Обогрев водительского сиденья
- Обогрев пассажирского сиденья
- Обогрев задних сидений
- Обогрев переднего стекла
- Обогрев заднего стекла
- Обогрев зеркал
- Обогрев руля

## Кнопки управления

- **Охрана Вкл** - Включить систему охраны
- **Охрана Выкл** - Выключить систему охраны
- **Автозапуск Вкл** - Включить автозапуск двигателя
- **Автозапуск Выкл** - Выключить автозапуск двигателя

## Примеры автоматизаций

### Уведомление при открытии водительской двери

```yaml
automation:
  - alias: "Prizrak: Открыта водительская дверь"
    trigger:
      - platform: state
        entity_id: binary_sensor.my_car_driver_door
        to: "on"
    action:
      - service: notify.mobile_app
        data:
          title: "Оповещение о машине"
          message: "Водительская дверь была открыта!"
```

### Включение охраны ночью

```yaml
automation:
  - alias: "Prizrak: Включить охрану ночью"
    trigger:
      - platform: time
        at: "23:00:00"
    action:
      - service: button.press
        target:
          entity_id: button.my_car_guard_on
```

### Уведомление о низком заряде батареи

```yaml
automation:
  - alias: "Prizrak: Предупреждение о низком заряде батареи"
    trigger:
      - platform: numeric_state
        entity_id: sensor.my_car_battery_voltage
        below: 11.5
    action:
      - service: notify.mobile_app
        data:
          title: "Низкий заряд батареи автомобиля"
          message: "Напряжение батареи {{ states('sensor.my_car_battery_voltage') }}В"
```

### Уведомление при тревоге

```yaml
automation:
  - alias: "Prizrak: Сработала сигнализация"
    trigger:
      - platform: state
        entity_id: sensor.my_car_alarm
    condition:
      - condition: template
        value_template: "{{ states('sensor.my_car_alarm') not in ['Unknown', 'None', 'unavailable'] }}"
    action:
      - service: notify.mobile_app
        data:
          title: "⚠️ ТРЕВОГА!"
          message: "Сигнализация: {{ states('sensor.my_car_alarm') }}"
          data:
            priority: high
```

## Устранение неполадок

### Интеграция не загружается

1. Проверьте логи Home Assistant: **Настройки** → **Система** → **Логи**
2. Ищите ошибки, связанные с "prizrak"
3. Проверьте учетные данные на monitoring.tecel.ru

### Устройства не появляются

1. Подождите 30-60 секунд после добавления интеграции
2. Убедитесь, что устройства видны на monitoring.tecel.ru
3. Перезапустите Home Assistant
4. Проверьте логи на наличие ошибок подключения

### Сенсоры показывают "недоступен"

1. Проверьте интернет-соединение
2. Убедитесь, что monitoring.tecel.ru доступен
3. Проверьте логи Home Assistant на наличие ошибок WebSocket
4. Попробуйте удалить и заново добавить интеграцию

## Поддержка

- **Проблемы**: [GitHub Issues](https://github.com/SIMBOCOM/prizrak-ha/issues)

## Лицензия

Код распространяется по [лицензии MIT](LICENSE). Права на фирменную иконку остаются у её правообладателя.

## Благодарности

[Поблагодарить](https://pay.cloudtips.ru/p/aa2fce54)

Исходную интеграцию разработал [@dsultanr](https://github.com/dsultanr/prizrak-ha-integration).

Значок приложения «Призрак 2.0» принадлежит ТЭК электроникс. [Источник в App Store](https://apps.apple.com/ru/app/id1473587827).

## Отказ от ответственности

Автор исходного проекта указывает модель Призрак-8XL/Slim/7.6. Версия без GPS проверена на Home Assistant Core 2026.11.2 и на демоаккаунте сервиса.

Это неофициальная интеграция и не связана с компанией ТЭК электроникс или сервисом monitoring.tecel.ru.
