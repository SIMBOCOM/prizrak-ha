# Инструкция по установке Prizrak HA Integration

## Установка через HACS

Откройте HACS → ⋮ → «Пользовательские репозитории», добавьте `https://github.com/SIMBOCOM/prizrak-ha-no-gps` с типом **Integration** и скачайте **Prizrak Monitoring без GPS**. Перезапустите Home Assistant.

## Ручная установка версии без GPS

Для библиотеки `websockets` версии 17.4 требуется Python 3.11 или новее. При запуске Home Assistant проверяет зависимость `websockets>=17.4` и при необходимости устанавливает её.

1. Распакуйте архив и скопируйте папку `custom_components/prizrak` в `/config/custom_components/`.
2. Если Prizrak уже установлен, замените его каталог целиком. После перезапуска интеграция уберёт свои прежние GPS-сущности. Если вы добавляли GPS на панель вручную, отредактируйте соответствующие карточки.
3. Для обновлений этой версии выбирайте в HACS репозиторий `SIMBOCOM/prizrak-ha-no-gps`.

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

### Ошибки аутентификации
1. Проверьте правильность email/пароля на monitoring.tecel.ru
2. Убедитесь, что аккаунт активен
3. Проверьте логи: Settings → System → Logs

### Сенсоры показывают "unavailable"
1. Проверьте подключение к интернету
2. Проверьте доступность monitoring.tecel.ru
3. Проверьте логи на наличие WebSocket ошибок
4. Попробуйте удалить и заново добавить интеграцию

## Дополнительная информация

- **Документация**: [README.md](README.md)
- **GitHub**: https://github.com/SIMBOCOM/prizrak-ha-no-gps
- **Issues**: https://github.com/SIMBOCOM/prizrak-ha-no-gps/issues
