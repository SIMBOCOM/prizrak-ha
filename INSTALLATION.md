# Инструкция по установке Prizrak HA Integration

## Установка через HACS

Откройте HACS → ⋮ → «Пользовательские репозитории», добавьте `https://github.com/SIMBOCOM/prizrak-ha` с типом **Integration** и скачайте **Prizrak Monitoring без GPS**. Перезапустите Home Assistant.

<a id="switch-repository"></a>

## Переход с исходной интеграции в Marketplace

В Home Assistant 2026.11 сообщение `The prizrak directory belongs to dsultanr/prizrak-ha-integration` означает, что Marketplace считает исходный репозиторий владельцем папки `custom_components/prizrak`.

Если вы только скачали исходную версию и ещё не настраивали Prizrak, удалите исходную версию в Marketplace и установите **Prizrak Monitoring без GPS** из `SIMBOCOM/prizrak-ha`.

Если Prizrak уже настроен, сохраните его запись в «Устройства и службы». Кнопка «Удалить и деинсталлировать» удалит и эту запись.

1. Сделайте резервную копию Home Assistant. В файловом менеджере переместите **всю папку** `/config/custom_components/prizrak` за пределы `custom_components`, например в `/config/prizrak-before-switch`. Выберите свободное имя и оставьте Home Assistant запущенным.
2. Откройте [интеграцию Marketplace](https://my.home-assistant.io/redirect/integration/?domain=marketplace). В меню ⋮ её записи выберите «Перезагрузить». После перезагрузки откройте карточку `dsultanr/prizrak-ha-integration` и убедитесь, что она показывает «Не установлено».
3. Установите **Prizrak Monitoring без GPS** из `SIMBOCOM/prizrak-ha`. Дождитесь окончания установки и перезапустите Home Assistant.
4. Откройте «Настройки → Устройства и службы → Prizrak Monitoring» и проверьте своё устройство и его сущности охраны. При переходе на версию без GPS прежние GPS-сущности удаляются.

Если ошибка владения осталась и новая установка не началась, верните сохранённую папку на прежнее место до перезапуска Home Assistant.

## Ручная установка версии без GPS

Для библиотеки `websockets` версии 17.4 требуется Python 3.11 или новее. При запуске Home Assistant проверяет зависимость `websockets>=17.4` и при необходимости устанавливает её.

1. Распакуйте архив и скопируйте папку `custom_components/prizrak` в `/config/custom_components/`.
2. Если Prizrak уже установлен, замените его каталог целиком. После перезапуска интеграция уберёт свои прежние GPS-сущности. Если вы добавляли GPS на панель вручную, отредактируйте соответствующие карточки.
3. Копирование файлов вручную сохраняет прежнюю привязку Marketplace. Для получения обновлений из `SIMBOCOM/prizrak-ha` выполните [переход с исходной интеграции](#switch-repository), если она была установлена через магазин.

### Перезапуск Home Assistant
```bash
# Перезапустите Home Assistant
sudo systemctl restart home-assistant@homeassistant

# Или через UI: Settings → System → Restart
```

### Добавление интеграции при первой установке
1. Откройте Home Assistant
2. Перейдите в **Settings** → **Devices & Services**
3. Нажмите **"+ ADD INTEGRATION"**
4. Найдите **"Prizrak Monitoring"**
5. Введите email и пароль от monitoring.tecel.ru
6. Нажмите **Submit**

## Проверка установки

### 1. Проверьте логи
```bash
# Откройте логи Home Assistant
tail -f /home/homeassistant/.homeassistant/home-assistant.log | grep prizrak
```

### 2. Проверьте наличие сенсоров
1. Перейдите в **Developer Tools** → **States**
2. Найдите сенсоры `sensor.prizrak_*`, `binary_sensor.prizrak_*`, `button.prizrak_*`

### 3. Проверьте устройства
1. Перейдите в **Settings** → **Devices & Services** → **Prizrak Monitoring**
2. Должны отображаться ваши устройства

## Удаление интеграции

### Через UI (рекомендуется)
1. Settings → Devices & Services
2. Найдите "Prizrak Monitoring"
3. Нажмите три точки (⋮) → "Delete"

### Вручную
```bash
# Удалите папку интеграции
rm -rf /path/to/homeassistant/custom_components/prizrak

# Перезапустите Home Assistant
sudo systemctl restart home-assistant@homeassistant
```

## Устранение проблем

### Интеграция не появляется в списке
1. Проверьте, что папка `custom_components/prizrak` существует
2. Проверьте права доступа: `custom_components/prizrak`
3. Перезапустите Home Assistant
4. Очистите кеш браузера (Ctrl+Shift+R)

### Ошибки входа

Откройте «Настройки → Система → Журнал сервера» и поищите `TECEL Passport`. Начиная с 1.0.5 запись указывает этап входа и тип ошибки. При ошибке соединения TCP журнал также содержит номер системной ошибки (`errno`).

Для Home Assistant Container доступ к TECEL можно проверить с Docker-хоста. Подставьте имя своего контейнера. Команда запрашивает общедоступную версию сервиса и при успехе выводит `200`.

```sh
docker exec homeassistant python -c "import urllib.request; print(urllib.request.urlopen('https://monitoring.tecel.ru/passport/version_data', timeout=10).status)"
```

### Сенсоры показывают "unavailable"
1. Проверьте подключение к интернету
2. Проверьте доступность monitoring.tecel.ru
3. Проверьте логи на наличие WebSocket ошибок
4. Попробуйте удалить и заново добавить интеграцию

## Дополнительная информация

- **Документация**: [README.md](README.md)
- **GitHub**: https://github.com/SIMBOCOM/prizrak-ha
- **Issues**: https://github.com/SIMBOCOM/prizrak-ha/issues
