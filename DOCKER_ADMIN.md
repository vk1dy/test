# 🐳 Docker — Администрирование портфолио

Полное руководство: как запускать, останавливать, обновлять и отлаживать
контейнер с фотопортфолио на Ubuntu-сервере.

---

## Содержание

1. [Зависимости и что от чего зависит](#1-зависимости-и-что-от-чего-зависит)
2. [Установка Docker на Ubuntu](#2-установка-docker-на-ubuntu)
3. [Структура файлов для Docker](#3-структура-файлов-для-docker)
4. [Dockerfile — разбор по строкам](#4-dockerfile--разбор-по-строкам)
5. [docker-compose.yml — разбор по строкам](#5-docker-composeyml--разбор-по-строкам)
6. [Ежедневные команды](#6-ежедневные-команды)
7. [Обновление кода на сервере](#7-обновление-кода-на-сервере)
8. [Логи и отладка](#8-логи-и-отладка)
9. [Типичные ошибки и их решения](#9-типичные-ошибки-и-их-решения)
10. [Настройка Nginx + HTTPS (продакшен)](#10-настройка-nginx--https-продакшен)

---

## 1. Зависимости и что от чего зависит

```
Ubuntu-сервер
└── Docker Engine          ← системный демон, управляет контейнерами
    └── Docker Compose     ← плагин для запуска по docker-compose.yml
        └── Контейнер portfolio
            ├── Python 3.12-slim   ← базовый образ (скачивается с Docker Hub)
            ├── gunicorn           ← WSGI-сервер, запускает Flask
            │   └── app.py (Flask) ← твоё приложение
            │       └── requests   ← HTTP-клиент → Яндекс API
            └── Jinja2 templates   ← HTML-шаблоны
```

**Цепочка запроса от браузера:**
```
Браузер → [80/443] → Nginx (опционально) → [5000] → gunicorn → Flask → Яндекс API
```

**Что нужно для работы:**
- `YANDEX_TOKEN` — без него приложение запустится, но все запросы к API вернут 401
- Папки из `ALBUM_PATHS` должны существовать на Яндекс Диске
- Порт 5000 должен быть открыт (или проксирован через Nginx на 80/443)

---

## 2. Установка Docker на Ubuntu

```bash
# Обновить пакеты
sudo apt update && sudo apt upgrade -y

# Установить зависимости
sudo apt install -y ca-certificates curl gnupg lsb-release

# Добавить официальный GPG-ключ Docker
sudo install -m 0755 -d /etc/apt/keyrings
curl -fsSL https://download.docker.com/linux/ubuntu/gpg \
  | sudo gpg --dearmor -o /etc/apt/keyrings/docker.gpg
sudo chmod a+r /etc/apt/keyrings/docker.gpg

# Добавить репозиторий Docker
echo \
  "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.gpg] \
  https://download.docker.com/linux/ubuntu \
  $(. /etc/os-release && echo "$VERSION_CODENAME") stable" \
  | sudo tee /etc/apt/sources.list.d/docker.list > /dev/null

# Установить Docker Engine и Compose плагин
sudo apt update
sudo apt install -y docker-ce docker-ce-cli containerd.io docker-compose-plugin

# Запустить Docker и включить автозапуск
sudo systemctl enable --now docker

# Добавить текущего пользователя в группу docker (чтобы не писать sudo)
sudo usermod -aG docker $USER

# !! Применить группу без перезагрузки !!
newgrp docker

# Проверить установку
docker --version         # Docker version 26.x.x
docker compose version   # Docker Compose version v2.x.x
```

---

## 3. Структура файлов для Docker

```
fotoportfolio/
├── Dockerfile           ← инструкция по сборке образа
├── docker-compose.yml   ← конфигурация запуска (порты, env, тома)
├── .dockerignore        ← что НЕ копировать в образ
├── requirements.txt     ← Python-зависимости
├── app.py
└── templates/
    ├── base.html
    ├── index.html
    ├── album.html
    └── landing.html
```

### Dockerfile

```dockerfile
# Базовый образ: Python 3.12, минимальный (без лишних пакетов)
FROM python:3.12-slim

# Рабочая директория внутри контейнера
WORKDIR /app

# Сначала копируем ТОЛЬКО requirements.txt
# Это кэш-оптимизация: если код изменился, но зависимости нет —
# Docker не будет переустанавливать пакеты (используется кэш слоя)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Теперь копируем весь остальной код
COPY . .

# Порт, который слушает gunicorn внутри контейнера
EXPOSE 5000

# Команда запуска:
# --bind 0.0.0.0:5000  → слушать все сетевые интерфейсы
# --workers 2          → 2 параллельных воркера (хватит для небольшого сайта)
# --timeout 60         → таймаут запроса 60 сек (нужно для проксирования больших фото)
# app:app              → файл app.py, объект app = Flask(...)
CMD ["gunicorn", "--bind", "0.0.0.0:5000", "--workers", "2", "--timeout", "60", "app:app"]
```

### .dockerignore

```
# Не копировать в образ:
__pycache__/
*.pyc
*.pyo
.env
.git/
.gitignore
*.md
.DS_Store
```

### docker-compose.yml

```yaml
services:
  portfolio:
    build: .                      # собрать образ из текущей папки (Dockerfile)
    restart: unless-stopped       # перезапускать при падении, но не после docker stop
    ports:
      - "5000:5000"               # хост:контейнер
    environment:
      - YANDEX_TOKEN=AgAAAAAxxxxx
      - SITE_TITLE=Моё Портфолио
      - SITE_AUTHOR=Иван Иванов
      - ALBUM_PATHS=/Фото/Свадьба,/Фото/Природа
    # Опционально — монтировать шаблоны с хоста (для разработки без пересборки):
    # volumes:
    #   - ./templates:/app/templates
```

---

## 4. Dockerfile — разбор по строкам

| Строка | Что делает | Почему важно |
|--------|-----------|--------------|
| `FROM python:3.12-slim` | Базовый образ | `-slim` весит ~50MB вместо ~350MB у полного |
| `WORKDIR /app` | Рабочая директория | Все дальнейшие команды выполняются тут |
| `COPY requirements.txt .` | Только зависимости | Отдельный слой → кэш pip при изменении кода |
| `RUN pip install ...` | Установка пакетов | `--no-cache-dir` уменьшает размер образа |
| `COPY . .` | Весь код | После установки зависимостей |
| `EXPOSE 5000` | Документация порта | Не открывает порт — только метка |
| `CMD [...]` | Команда запуска | Переопределяется в compose через `command:` |

---

## 5. docker-compose.yml — разбор по строкам

| Параметр | Что делает |
|----------|-----------|
| `build: .` | Ищет `Dockerfile` в текущей папке и собирает образ |
| `restart: unless-stopped` | Авторестарт при крэше и при перезагрузке сервера. Останавливается только через `docker compose stop` |
| `ports: "5000:5000"` | Пробрасывает порт 5000 хоста на 5000 контейнера |
| `environment:` | Переменные окружения — читаются в `app.py` через `os.environ.get()` |

---

## 6. Ежедневные команды

### Запуск

```bash
cd ~/fotoportfolio

# Первый запуск или после изменения кода/Dockerfile
docker compose up -d --build

# Запуск без пересборки (если код не менялся)
docker compose up -d
```

### Остановка

```bash
# Остановить контейнер (можно снова запустить через up -d)
docker compose stop

# Остановить И удалить контейнер (образ сохраняется)
docker compose down

# Остановить, удалить контейнер И образ (пересборка с нуля)
docker compose down --rmi local
```

### Статус

```bash
# Запущен ли контейнер?
docker compose ps

# Все контейнеры на сервере
docker ps -a

# Использование ресурсов (CPU, RAM) в реальном времени
docker stats
```

### Перезапуск

```bash
# Мягкий перезапуск (без пересборки)
docker compose restart

# Жёсткий перезапуск с пересборкой (после изменения кода)
docker compose down && docker compose up -d --build
```

---

## 7. Обновление кода на сервере

### Вариант А — копировать файлы вручную (простой)

```bash
# На локальной машине: скопировать изменённые файлы на сервер
scp templates/landing.html user@твой-сервер:~/fotoportfolio/templates/
scp app.py user@твой-сервер:~/fotoportfolio/

# На сервере: пересобрать и перезапустить
ssh user@твой-сервер
cd ~/fotoportfolio
docker compose up -d --build
```

### Вариант Б — через Git (рекомендуется)

```bash
# На сервере (один раз):
cd ~
git clone https://github.com/ты/fotoportfolio.git
cd fotoportfolio
docker compose up -d --build

# При каждом обновлении:
git pull
docker compose up -d --build
```

### Обновить только переменные окружения (без пересборки)

```bash
# Отредактировать docker-compose.yml
nano docker-compose.yml

# Перезапустить контейнер (образ не пересобирается)
docker compose down && docker compose up -d
```

### Обновить шаблоны БЕЗ пересборки (режим разработки)

Раскомментируй `volumes` в `docker-compose.yml`:
```yaml
volumes:
  - ./templates:/app/templates
```
Теперь Flask читает шаблоны прямо с хоста — достаточно сохранить `.html` файл
и обновить страницу в браузере. Пересборка не нужна.

> ⚠️ В продакшене этот том лучше закомментировать — шаблоны будут запечены в образ.

---

## 8. Логи и отладка

### Просмотр логов

```bash
# Последние 50 строк логов
docker compose logs --tail=50

# Логи в реальном времени (Ctrl+C для выхода)
docker compose logs -f

# Логи только с временными метками
docker compose logs -f -t

# Логи за последний час
docker compose logs --since=1h
```

### Зайти внутрь контейнера

```bash
# Открыть bash внутри запущенного контейнера
docker compose exec portfolio bash

# Внутри контейнера можно:
ls /app                          # проверить файлы
python -c "import flask; print(flask.__version__)"  # проверить пакеты
curl http://localhost:5000/      # проверить приложение изнутри
env | grep YANDEX                # проверить переменные окружения
exit                             # выйти
```

### Проверить переменные окружения в контейнере

```bash
docker compose exec portfolio env
```

### Проверить сеть

```bash
# Доступен ли сайт с сервера
curl -I http://localhost:5000/

# Открыт ли порт снаружи
ss -tlnp | grep 5000
```

### Размер образа

```bash
docker images | grep fotoportfolio
```

---

## 9. Типичные ошибки и их решения

### `port is already allocated`
```
Error: bind: address already in use
```
```bash
# Найти что занимает порт 5000
sudo ss -tlnp | grep 5000
# или
sudo lsof -i :5000

# Убить процесс (заменить PID)
sudo kill -9 <PID>

# Или сменить порт в docker-compose.yml
ports:
  - "8080:5000"   # теперь сайт на :8080
```

### `TemplateNotFound`
```
jinja2.exceptions.TemplateNotFound: album.html
```
```bash
# Проверить что файл существует
ls ~/fotoportfolio/templates/

# Пересобрать образ (файл мог не попасть в образ)
docker compose up -d --build
```

### `401 Unauthorized` от Яндекс API
```bash
# Проверить что токен передаётся
docker compose exec portfolio env | grep YANDEX

# Проверить токен напрямую
curl -H "Authorization: OAuth ВАШ_ТОКЕН" \
  "https://cloud-api.yandex.net/v1/disk/"
# Должен вернуть JSON с информацией о диске
```

### Контейнер падает сразу после запуска
```bash
# Запустить без -d чтобы видеть ошибки сразу
docker compose up

# Или посмотреть логи упавшего контейнера
docker compose logs
```

### Образ не обновляется после изменения кода
```bash
# Принудительная пересборка без кэша
docker compose build --no-cache
docker compose up -d
```

### Нет места на диске
```bash
# Сколько занимает Docker
docker system df

# Удалить неиспользуемые образы, контейнеры, тома
docker system prune -f

# Удалить ВСЁ включая остановленные контейнеры и все образы
docker system prune -af
```

---

## 10. Настройка Nginx + HTTPS (продакшен)

### Установка Nginx и Certbot

```bash
sudo apt install -y nginx certbot python3-certbot-nginx
```

### Конфиг Nginx

```bash
sudo nano /etc/nginx/sites-available/portfolio
```

```nginx
server {
    listen 80;
    server_name твой-домен.ru www.твой-домен.ru;

    # Certbot сам добавит HTTPS-блок ниже
    location / {
        proxy_pass         http://127.0.0.1:5000;
        proxy_http_version 1.1;
        proxy_set_header   Host              $host;
        proxy_set_header   X-Real-IP         $remote_addr;
        proxy_set_header   X-Forwarded-For   $proxy_add_x_forwarded_for;
        proxy_set_header   X-Forwarded-Proto $scheme;

        # Важно для стриминга картинок — не буферизовать
        proxy_buffering    off;
        proxy_read_timeout 120s;

        # Разрешить загрузку больших файлов
        client_max_body_size 200M;
    }
}
```

```bash
# Активировать конфиг
sudo ln -s /etc/nginx/sites-available/portfolio /etc/nginx/sites-enabled/
sudo nginx -t        # проверить синтаксис
sudo systemctl reload nginx

# Получить SSL-сертификат (Let's Encrypt, бесплатно)
sudo certbot --nginx -d твой-домен.ru -d www.твой-домен.ru

# Certbot автоматически обновит конфиг под HTTPS
# Автообновление сертификата — уже настроено через systemd timer
sudo systemctl status certbot.timer
```

После этого в `docker-compose.yml` порт можно оставить только локально:
```yaml
ports:
  - "127.0.0.1:5000:5000"   # доступен только с localhost (только через Nginx)
```

### Порядок запуска сервисов

```
1. docker compose up -d    → gunicorn слушает 127.0.0.1:5000
2. sudo systemctl start nginx  → Nginx проксирует :80/:443 → :5000
```

При перезагрузке сервера оба сервиса стартуют автоматически:
- Docker: `restart: unless-stopped` в compose
- Nginx: `sudo systemctl enable nginx`

---

## Шпаргалка — самые нужные команды

```bash
# Запустить (пересобрать образ)
docker compose up -d --build

# Посмотреть логи
docker compose logs -f

# Перезапустить без пересборки
docker compose restart

# Остановить
docker compose down

# Зайти внутрь
docker compose exec portfolio bash

# Статус
docker compose ps

# Очистить мусор
docker system prune -f
```
