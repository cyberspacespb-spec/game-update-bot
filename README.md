# Game Update Notifier Bot

Этот репозиторий содержит Telegram-бота, который отслеживает обновления игр и рассылает подписчикам уведомления.
Поддерживаемые источники: Steam (CS2, Dota 2, PUBG), Epic (Fortnite), Riot (LoL, Valorant).

## Быстрый старт (Render.com)

1. Зарегистрируйся на https://render.com и создай новый Web Service.
2. Подключи GitHub-репозиторий с этим кодом.
3. Задай переменные окружения в настройках сервиса:
   - `TELEGRAM_TOKEN` — токен от BotFather.
   - `CHECK_INTERVAL_SEC` — (опционально) интервал проверки в секундах, по умолчанию 1800 (30 минут).
4. Команда запуска: `python bot.py`.
5. Деплой — и бот запущен на Render.

## Локальный запуск
1. Установи зависимости: `pip install -r requirements.txt`
2. Экспортируй переменную окружения (Linux/macOS):
   ```bash
   export TELEGRAM_TOKEN="your_token_here"
   ```
   В Windows PowerShell:
   ```powershell
   setx TELEGRAM_TOKEN "your_token_here"
   ```
3. Запусти: `python bot.py`

## Файлы
- `bot.py` — основной код бота
- `subscriptions.json` — автоматически создаётся и хранит подписки и последние новости

## Замечания
- Бот использует long-polling (подходит для бесплатного хостинга Render).
- Если нужен более надёжный продакшен, стоит добавить обработку ошибок, retry и мониторинг.
