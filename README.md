# Apache Monitoring Stack

Проект разработан и успешно внедрён в продакшен-среду коммерческого веб-сервера. 
Задача: обеспечить централизованный сбор логов, настройку алертинга и визуализацию трафика без простоя сервиса.

Полноценный мониторинг веб-сервера Apache/Nginx на базе Grafana Loki, Promtail и Grafana. Все настройки описаны в коде и разворачиваются автоматически.

## Возможности

- Сбор и анализ access-логов в реальном времени
- 6 преднастроенных дашбордов:
  - **Обзор Apache**: общее количество запросов, ошибки, топ IP и страниц
  - **Трафик по сайтам**: трафик и RPS в разрезе виртуальных хостов
  - **Ошибки Apache (4xx/5xx)**: частота ошибок, топ 404 страниц
  - **Угрозы безопасности**: подозрительная активность, атаки, боты
  - **Детализация по IP**: логи и статистика по конкретному IP
  - **Активные алерты**: сводка сработавших алертов
- Настроенные алерты:
  - Всплеск ошибок 5xx (относительно предыдущего периода)
  - Высокий трафик с одного IP (более 200 rps)
  - Попытка SQL-инъекции (15+ подозрительных запросов за 10 минут)
- Автоматический provisioning Grafana (дашборды, источники данных, правила алертов)
- Исключение доверенных IP из статистики (через файл `exclude_ips.txt`)
- Поддержка сжатых логов (.gz)

## Скриншоты дашбордов

![Обзор Apache](Dashboard%20Обзор%20Apache.png)
![Ошибки Apache](Dashboard%20Ошибки%20Apache.png)
![Угрозы](Dashboard%20Угроза.png)
![Панель](Dashboard%20Панель.png)
![Трафик](Dashboard%20Трафик.png)

## Быстрый старт

1. Убедитесь, что установлены Docker и Docker Compose.
2. Склонируйте репозиторий:

    git clone https://github.com/al-kv/apache-monitoring-stack.git
    cd apache-monitoring-stack

3. Создайте файл `.env` на основе примера и задайте пароли:

    cp .env.example .env
    nano .env

4. В файле `docker-compose.yml` укажите правильный путь к логам веб-сервера в секции `promtail.volumes` (по умолчанию `/var/www/www-root/data/logs`).
5. Запустите стек:

    docker compose up -d

6. Откройте Grafana по адресу `http://localhost:3000` (логин и пароль из `.env`).

## Структура проекта

- `docker-compose.yml` – основной файл запуска (healthcheck, лимиты ресурсов)
- `loki/` – конфигурация Loki (хранение 30 дней)
- `promtail/` – конфигурация Promtail (динамическое исключение IP через `exclude_ips.txt`)
- `grafana/provisioning/` – автоматическая настройка Grafana:
  - `datasources/` – источник данных Loki
  - `dashboards/` – JSON-модели дашбордов
  - `alerting/` – правила алертов (`rules.yaml`), маршрутизация (`policies.yaml`) и точки контакта
- `scripts/` – вспомогательные скрипты (например, `fix-dashboards.py`)
- `.github/workflows/ci.yml` – CI пайплайн (валидация конфигов)
- `.env.example` – пример файла с переменными окружения

## Безопасность

- Все секреты вынесены в файл `.env` (не коммитится в репозиторий)
- Grafana по умолчанию слушает только на `127.0.0.1:3000`; для публичного доступа используйте reverse proxy (Nginx) с HTTPS
- Смените пароль администратора после первого входа

## Используемые технологии

- Grafana Loki 2.9.10 – агрегация и хранение логов
- Promtail 2.9.10 – сбор и отправка логов
- Grafana 10.4.3 – визуализация и алертинг
- Docker Compose – оркестрация контейнеров

## Known fixes (после ревью 2026-10)

- ✅ Все datasource/dashboard/alerting **действительно** провижинятся (добавлен volume для `datasources/`).
- ✅ `Loki` больше не публикуется наружу; healthcheck для Loki и Grafana, `depends_on: service_healthy`.
- ✅ Алерты используют `status`-label (`{status=~"5.."}`) вместо дорогого line-фильтра.
- ✅ Promtail хранит **только** низкокардинальные labels (`site`, `status`, `method`). `ip`, `path`, `bytes`, `user_agent` извлекаются через `| regexp` в LogQL.
- ✅ Убрано high-cardinality поле `bytes` из labels (было «почти уникально на запрос»).
- ✅ Email-адрес получателя алертов вынесен в `.env` (`GF_ALERT_EMAIL`).
- ✅ Маршрутизация алертов — через `policies.yaml` (правильная схема Grafana 10.x).
- ✅ `GF_SECURITY_ADMIN_PASSWORD` обязателен: без него `docker compose up` падает на старте.
- ✅ CI валидирует `docker compose config`, YAML, JSON и shell-скрипты.

## Backup & Restore (обязательно для прода)

Критичные тома:

| Том | Что внутри |
|---|---|
| `loki_data` | индексы и чанки логов (retention 30d) |
| `grafana_data` | БД Grafana, пользователи, состояние алертов |
| `promtail_positions` | позиции чтения логов (без него после рестарта — переиндексация) |

Пример бэкапа (cron, ежедневно 03:00):

    #!/usr/bin/env bash
    set -euo pipefail
    STAMP=$(date +%F_%H%M)
    DEST=/var/backups/apache-monitoring
    mkdir -p "$DEST"
    docker run --rm \
      -v apache-monitoring-stack_loki_data:/data:ro \
      -v "$DEST":/backup \
      alpine tar czf "/backup/loki_${STAMP}.tgz" -C /data .
    docker run --rm \
      -v apache-monitoring-stack_grafana_data:/data:ro \
      -v "$DEST":/backup \
      alpine tar czf "/backup/grafana_${STAMP}.tgz" -C /data .
    find "$DEST" -name '*.tgz' -mtime +14 -delete

### Проверено

| Компонент | Версия | Статус |
|---|---|---|
| Grafana | 10.4.3 | ✅ |
| Loki | 2.9.10 | ✅ |
| Promtail | 2.9.10 | ✅ |
| Docker Compose | v2.x | ✅ |

## Лицензия

MIT
