# 📸 Яндекс Диск Фотопортфолио — Документация

> Полное руководство по структуре кода, кастомизации и расширению функционала.

---

## Содержание

1. [Структура проекта](#1-структура-проекта)
2. [Как работает приложение](#2-как-работает-приложение)
3. [Файл app.py — бэкенд](#3-файл-apppy--бэкенд)
4. [Шаблоны — фронтенд](#4-шаблоны--фронтенд)
5. [Переменные окружения](#5-переменные-окружения)
6. [Частые задачи — что и где менять](#6-частые-задачи--что-и-где-менять)
   - [Сменить шрифт](#61-сменить-шрифт)
   - [Сменить цвета и тему](#62-сменить-цвета-и-тему)
   - [Повысить разрешение превью](#63-повысить-разрешение-превью)
   - [Добавить разделы на главной](#64-добавить-разделы-на-главной)
   - [Загрузка папки с сайта](#65-загрузка-папки-прямо-с-сайта)
7. [Маршруты (Routes) — справочник](#7-маршруты-routes--справочник)
8. [Архитектурные решения и почему они такие](#8-архитектурные-решения-и-почему-они-такие)
9. [Docker и деплой](#9-docker-и-деплой)
10. [Идеи для дальнейшего развития](#10-идеи-для-дальнейшего-развития)

---

## 1. Структура проекта

```
fotoportfolio/
│
├── app.py                  # Весь бэкенд: Flask-маршруты, работа с Яндекс API
│
├── requirements.txt        # Python-зависимости
├── Dockerfile              # Сборка Docker-образа
├── docker-compose.yml      # Запуск контейнера с переменными окружения
│
└── templates/              # HTML-шаблоны (Jinja2)
    ├── base.html           # Базовый шаблон: nav, footer, lightbox, общие стили
    ├── index.html          # Главная страница — сетка альбомов
    └── album.html          # Страница альбома — сетка фотографий
```

**Нет папки `static/`** — все стили и скрипты написаны прямо внутри шаблонов тегами `<style>` и `<script>`. Это упрощает структуру для небольшого проекта, но при росте кода стоит вынести их в отдельные файлы (см. раздел 10).

---

## 2. Как работает приложение

```
Браузер пользователя
       │
       │  GET /
       ▼
   Flask (app.py)
       │
       │  requests.get(Яндекс API)
       ▼
  Яндекс Диск API ──► список файлов/папок
       │
       │  render_template(index.html, albums=[...])
       ▼
   Браузер получает HTML со списком альбомов

       │
       │  <img src="/proxy/preview?url=...">
       ▼
   Flask /proxy/preview
       │
       │  requests.get(превью-урл от Яндекса, headers=OAuth)
       ▼
   Картинка отдаётся браузеру (Яндекс требует токен — поэтому нужен прокси)
```

**Почему нужен прокси?**
Яндекс отдаёт превью и файлы только с заголовком `Authorization: OAuth <токен>`. Браузер не может добавить этот заголовок самостоятельно в тег `<img>`, поэтому Flask проксирует запросы — получает картинку от Яндекса и передаёт её браузеру.

---

## 3. Файл `app.py` — бэкенд

### 3.1 Конфигурация (верх файла)

```python
YANDEX_TOKEN = os.environ.get("YANDEX_TOKEN", "")
YANDEX_API   = "https://cloud-api.yandex.net/v1/disk/resources"
SITE_TITLE   = os.environ.get("SITE_TITLE", "Portfolio")
SITE_AUTHOR  = os.environ.get("SITE_AUTHOR", "")
ALBUM_PATHS  = [p.strip() for p in os.environ.get("ALBUM_PATHS", "/").split(",") if p.strip()]
IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".gif", ".webp", ".heic", ".tiff"}
```

| Переменная | Что делает |
|---|---|
| `YANDEX_TOKEN` | OAuth-токен для Яндекс API. Берётся из env |
| `YANDEX_API` | Базовый URL Яндекс Диск API v1 |
| `SITE_TITLE` | Название сайта — отображается в nav и title страницы |
| `SITE_AUTHOR` | Имя автора — отображается в hero и footer |
| `ALBUM_PATHS` | Список папок на Яндекс Диске через запятую |
| `IMAGE_EXTENSIONS` | Какие расширения считать фотографиями |

**Добавить новый тип файла** (например, `.avif`):
```python
IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".gif", ".webp", ".heic", ".tiff", ".avif"}
```

---

### 3.2 Функция `yd_list_folder(path, limit)`

```python
def yd_list_folder(path: str, limit: int = 200) -> list[dict]:
```

Запрашивает содержимое папки на Яндекс Диске. Возвращает список словарей с полями:
- `name` — имя файла
- `type` — `"file"` или `"dir"`
- `mime_type` — MIME-тип (`image/jpeg` и т.д.)
- `preview` — URL превью (временный, требует токен)
- `path` — путь на диске (`disk:/Фото/img001.jpg`)
- `created` — дата создания

**Параметр `fields`** в запросе — это оптимизация: Яндекс API возвращает только нужные поля, а не весь объект. Если понадобится новое поле (например, `size` — размер файла), добавь его туда:

```python
"fields": "_embedded.items.name,...,_embedded.items.size",
```

**Параметр `preview_size`** — размер превью. Подробнее в разделе 6.3.

**`limit: int = 200`** — максимум файлов за один запрос. Яндекс API поддерживает до 1000. Для больших альбомов увеличь или реализуй пагинацию (раздел 10).

---

### 3.3 Функция `get_download_url(path)`

```python
def get_download_url(path: str) -> str:
```

Получает **временную прямую ссылку** на скачивание файла. Эта ссылка действительна несколько минут и не требует токена — поэтому её можно использовать в браузере напрямую.

Используется в маршруте `/proxy/full` для показа полноразмерных фотографий в лайтбоксе.

---

### 3.4 Маршрут `/proxy/preview`

```python
@app.route("/proxy/preview")
def proxy_preview():
    url = request.args.get("url")
```

Принимает `?url=<превью-урл-от-яндекса>`, добавляет токен и возвращает картинку браузеру.

Заголовок `Cache-Control: public, max-age=3600` кэширует превью на 1 час в браузере — это важно для производительности при повторных посещениях.

---

### 3.5 Маршрут `/proxy/full`

```python
@app.route("/proxy/full")
def proxy_full():
    path = request.args.get("path")
```

Принимает `?path=disk:/Фото/img.jpg`, получает временную ссылку скачивания и стримит файл браузеру. Используется лайтбоксом для показа полного разрешения.

---

## 4. Шаблоны — фронтенд

### 4.1 `base.html` — основа всего

Содержит:
- **CSS-переменные** (`:root { ... }`) — централизованная тема
- **Стили навигации** (`nav`)
- **Стили футера** (`footer`)
- **Весь лайтбокс** — HTML, CSS и JS

Блоки Jinja2, которые переопределяют дочерние шаблоны:
```
{% block title %}    — <title> страницы
{% block head %}     — дополнительные <style> и мета
{% block content %}  — основной контент страницы
{% block scripts %}  — JS в конце страницы
```

### 4.2 CSS-переменные — главный инструмент кастомизации

Находятся в `base.html` в блоке `<style>`, раздел `:root`:

```css
:root {
  --bg: #0e0e0e;              /* фон страницы */
  --surface: #161616;         /* фон карточек и skeleton */
  --border: rgba(255,255,255,0.07);  /* цвет рамок */
  --text: #e8e4de;            /* основной текст */
  --muted: rgba(232,228,222,0.4);    /* приглушённый текст */
  --accent: #c8a97e;          /* золотой акцент */
  --accent2: #8fa89e;         /* второй акцент (зеленоватый) */
  --radius: 2px;              /* скругление углов */
  --font-display: 'Cormorant Garamond', Georgia, serif;  /* заголовки */
  --font-body: 'Jost', system-ui, sans-serif;            /* текст */
}
```

Изменение любой переменной здесь меняет весь сайт сразу.

---

## 5. Переменные окружения

Все настройки передаются через `docker-compose.yml`:

```yaml
environment:
  - YANDEX_TOKEN=AgAAAAAxxxxx     # обязательно
  - SITE_TITLE=Моё фото           # название сайта
  - SITE_AUTHOR=Иван Иванов       # имя автора
  - ALBUM_PATHS=/Фото/Свадьба,/Фото/Природа   # папки через запятую
```

После изменения `docker-compose.yml` — перезапусти:
```bash
docker compose down && docker compose up -d
```
(пересборка образа не нужна, т.к. код не менялся)

---

## 6. Частые задачи — что и где менять

### 6.1 Сменить шрифт

**Файл:** `base.html`

**Шаг 1.** Найди и замени строку подключения Google Fonts:
```html
<!-- Было -->
<link href="https://fonts.googleapis.com/css2?family=Cormorant+Garamond:ital,wght@0,300;0,400;0,600;1,300;1,400&family=Jost:wght@200;300;400&display=swap" rel="stylesheet">

<!-- Пример замены на другую пару шрифтов -->
<link href="https://fonts.googleapis.com/css2?family=Playfair+Display:ital,wght@0,400;0,700;1,400&family=DM+Sans:wght@300;400&display=swap" rel="stylesheet">
```

**Шаг 2.** Обнови CSS-переменные в `:root`:
```css
--font-display: 'Playfair Display', Georgia, serif;
--font-body: 'DM Sans', system-ui, sans-serif;
```

**Популярные пары для фотопортфолио:**

| Display (заголовки) | Body (текст) | Характер |
|---|---|---|
| `Cormorant Garamond` | `Jost` | Люксовый, утончённый (текущий) |
| `Playfair Display` | `DM Sans` | Классический редакционный |
| `Libre Baskerville` | `Source Sans 3` | Строгий, журнальный |
| `Fraunces` | `Outfit` | Современный, тёплый |
| `EB Garamond` | `Inter` | Минималистичный |

Найти шрифты: [fonts.google.com](https://fonts.google.com)

**Изменить размер шрифта заголовка альбома** (`album.html`):
```css
.album-title {
  font-size: clamp(2.2rem, 5vw, 3.8rem);  /* мин, предпочтительный, макс */
}
```

---

### 6.2 Сменить цвета и тему

**Файл:** `base.html`, раздел `:root`

**Светлая тема:**
```css
:root {
  --bg: #f5f2ee;
  --surface: #eeebe6;
  --border: rgba(0,0,0,0.08);
  --text: #1a1714;
  --muted: rgba(26,23,20,0.45);
  --accent: #8b5e3c;
  --accent2: #4a7c6f;
}
```

**Холодная тёмная тема:**
```css
:root {
  --bg: #0a0d12;
  --surface: #111520;
  --border: rgba(100,140,255,0.08);
  --text: #dde4f0;
  --muted: rgba(221,228,240,0.4);
  --accent: #6b9fff;
  --accent2: #9b7fff;
}
```

**Изменить цвет акцентной линии на главной (декоративная вертикальная линия):**
```css
/* index.html, .hero-line */
.hero-line {
  background: linear-gradient(to bottom, var(--accent), transparent);
  /* или конкретный цвет: */
  background: linear-gradient(to bottom, #ff6b6b, transparent);
}
```

---

### 6.3 Повысить разрешение превью

**Файл:** `app.py`, функция `yd_list_folder`

Найди параметр `preview_size` и замени значение:

```python
# Было:
"preview_size": "M",

# Варианты размеров Яндекс API:
# S  — 150px (маленький)
# M  — 300px (средний, текущий)
# L  — 500px
# XL — 800px
# XXL — 1024px
# XXXL — 1280px

# Для хорошего качества на экранах Retina:
"preview_size": "XL",

# Или конкретный размер в пикселях:
"preview_size": "800x600",
```

> ⚠️ Чем больше размер — тем дольше загрузка и больше трафика. `XL` (800px) — хороший баланс для большинства экранов. `XXXL` имеет смысл только если у пользователей очень быстрый интернет.

Также можно задать **разные размеры** для главной (обложки альбомов) и для страницы альбома. Для этого добавь второй параметр в вызов функции:

```python
# В app.py, функция yd_list_folder — добавь параметр:
def yd_list_folder(path: str, limit: int = 200, preview_size: str = "M") -> list[dict]:
    params = {
        ...
        "preview_size": preview_size,
    }

# В маршруте /album — запроси крупнее:
items = yd_list_folder(path, limit=500, preview_size="XL")

# В маршруте / (главная) — достаточно среднего:
items = yd_list_folder(folder_path, preview_size="M")
```

---

### 6.4 Добавить разделы на главном экране

Сейчас главная показывает альбомы из `ALBUM_PATHS`. Чтобы добавить **группировку по разделам** (например: «Свадьбы», «Репортаж», «Портреты»):

**Шаг 1.** В `docker-compose.yml` добавь переменную разделов:
```yaml
environment:
  - ALBUM_PATHS=/Фото/Свадьбы,/Фото/Репортаж,/Фото/Портреты
  - SECTIONS=Свадьбы:/Фото/Свадьбы|/Фото/Свадьба2;Репортаж:/Фото/Репортаж;Портреты:/Фото/Портреты
```

**Шаг 2.** В `app.py` добавь парсинг разделов в конфигурацию:
```python
# Парсим формат "Название:путь1|путь2;НазваниеN:путьN"
def parse_sections(env_str: str) -> list[dict]:
    sections = []
    if not env_str:
        return sections
    for section_str in env_str.split(";"):
        if ":" not in section_str:
            continue
        name, paths_str = section_str.split(":", 1)
        paths = [p.strip() for p in paths_str.split("|") if p.strip()]
        sections.append({"name": name.strip(), "paths": paths})
    return sections

SECTIONS = parse_sections(os.environ.get("SECTIONS", ""))
```

**Шаг 3.** В маршруте `/` передавай разделы в шаблон:
```python
@app.route("/")
def index():
    # ... существующий код сбора albums ...
    
    # Группируем по разделам если они заданы
    sections_data = []
    if SECTIONS:
        for section in SECTIONS:
            section_albums = [a for a in albums if a["path"] in section["paths"]]
            if section_albums:
                sections_data.append({
                    "name": section["name"],
                    "albums": section_albums
                })
    
    return render_template(
        "index.html",
        albums=albums,
        sections=sections_data,      # ← новое
        site_title=SITE_TITLE,
        site_author=SITE_AUTHOR,
        single_album=len(ALBUM_PATHS) == 1,
    )
```

**Шаг 4.** В `index.html` замени блок с сеткой альбомов:
```html
{% if sections %}
  {% for section in sections %}
  <div class="section-block">
    <h2 class="section-title">{{ section.name }}</h2>
    <div class="albums-grid">
      {% for album in section.albums %}
        {# ... карточка альбома ... #}
      {% endfor %}
    </div>
  </div>
  {% endfor %}
{% else %}
  {# обычная сетка без разделов #}
  <div class="albums-grid"> ... </div>
{% endif %}
```

Добавь стили для заголовка раздела в `index.html`:
```css
.section-block { margin-bottom: 5rem; }
.section-title {
  font-family: var(--font-display);
  font-size: 0.7rem;
  font-weight: 400;
  letter-spacing: 0.25em;
  text-transform: uppercase;
  color: var(--muted);
  padding: 0 3rem 1.5rem;
}
```

---

### 6.5 Загрузка папки прямо с сайта

Это наиболее сложная функция. Потребует: форму загрузки, маршрут в `app.py` и API Яндекса для загрузки файлов.

#### Бэкенд — новый маршрут в `app.py`

```python
import io
from flask import request, jsonify

@app.route("/upload", methods=["POST"])
def upload():
    """Загрузить файл на Яндекс Диск в указанную папку."""
    folder = request.form.get("folder", "/Загрузки")
    file   = request.files.get("file")
    
    if not file:
        return jsonify({"error": "Файл не передан"}), 400
    
    filename = file.filename
    dest_path = f"{folder.rstrip('/')}/{filename}"
    
    # 1. Получить URL для загрузки
    resp = requests.get(
        f"{YANDEX_API}/upload",
        headers=yd_headers(),
        params={"path": dest_path, "overwrite": "false"},
        timeout=15,
    )
    if resp.status_code == 409:
        return jsonify({"error": "Файл уже существует"}), 409
    resp.raise_for_status()
    upload_url = resp.json()["href"]
    
    # 2. Загрузить файл по полученному URL
    upload_resp = requests.put(
        upload_url,
        data=file.stream,
        headers={"Content-Type": file.content_type},
        timeout=120,
    )
    upload_resp.raise_for_status()
    
    return jsonify({"ok": True, "path": dest_path})
```

> ⚠️ **Безопасность:** обязательно добавь проверку токена или сессии перед разрешением загрузки, иначе кто угодно сможет заливать файлы на твой Яндекс Диск.

#### Простая защита паролем для загрузки

```python
UPLOAD_PASSWORD = os.environ.get("UPLOAD_PASSWORD", "")

@app.route("/upload", methods=["POST"])
def upload():
    if UPLOAD_PASSWORD:
        token = request.headers.get("X-Upload-Token", "")
        if token != UPLOAD_PASSWORD:
            return jsonify({"error": "Не авторизован"}), 403
    # ... остальной код ...
```

#### Фронтенд — форма загрузки

Добавь в `album.html` кнопку и форму (или отдельную страницу `/upload-page`):

```html
<!-- Кнопка в album-header -->
<button class="view-btn" onclick="toggleUpload()">↑ Загрузить</button>

<!-- Панель загрузки (скрыта по умолчанию) -->
<div id="upload-panel" style="display:none; padding: 2rem 3rem; border-bottom: 1px solid var(--border);">
  <div id="drop-zone" style="
    border: 1px dashed var(--border);
    border-radius: 4px;
    padding: 3rem;
    text-align: center;
    color: var(--muted);
    cursor: pointer;
    transition: border-color 0.2s;
  ">
    Перетащи фото сюда или <label for="file-input" style="color:var(--accent);cursor:pointer">выбери файлы</label>
    <input id="file-input" type="file" multiple accept="image/*" style="display:none">
  </div>
  <div id="upload-progress" style="margin-top:1rem;"></div>
</div>

<script>
const ALBUM_PATH = {{ album_path | tojson }};
const UPLOAD_PASSWORD = ""; // если нужен пароль — вставь здесь или запроси у пользователя

function toggleUpload() {
  const panel = document.getElementById('upload-panel');
  panel.style.display = panel.style.display === 'none' ? 'block' : 'none';
}

document.getElementById('file-input').onchange = e => uploadFiles(e.target.files);

const dropZone = document.getElementById('drop-zone');
dropZone.ondragover  = e => { e.preventDefault(); dropZone.style.borderColor = 'var(--accent)'; };
dropZone.ondragleave = () => dropZone.style.borderColor = 'var(--border)';
dropZone.ondrop      = e => { e.preventDefault(); dropZone.style.borderColor = 'var(--border)'; uploadFiles(e.dataTransfer.files); };

async function uploadFiles(files) {
  const progress = document.getElementById('upload-progress');
  for (const file of files) {
    const row = document.createElement('div');
    row.style.cssText = 'margin:0.5rem 0; font-size:0.8rem; color:var(--muted)';
    row.textContent = `↑ ${file.name} ...`;
    progress.appendChild(row);

    const formData = new FormData();
    formData.append('file', file);
    formData.append('folder', ALBUM_PATH);

    try {
      const resp = await fetch('/upload', {
        method: 'POST',
        headers: UPLOAD_PASSWORD ? {'X-Upload-Token': UPLOAD_PASSWORD} : {},
        body: formData,
      });
      const data = await resp.json();
      row.style.color = data.ok ? 'var(--accent2)' : '#e07070';
      row.textContent = data.ok ? `✓ ${file.name}` : `✗ ${file.name}: ${data.error}`;
    } catch(err) {
      row.style.color = '#e07070';
      row.textContent = `✗ ${file.name}: ошибка сети`;
    }
  }
}
</script>
```

---

## 7. Маршруты (Routes) — справочник

| Метод | URL | Что делает |
|---|---|---|
| GET | `/` | Главная страница — список альбомов |
| GET | `/album?path=/Фото/Свадьба` | Страница альбома — сетка фото |
| GET | `/api/albums` | JSON-список альбомов (для AJAX/внешних клиентов) |
| GET | `/api/images?path=/Фото/Свадьба` | JSON-список фото в папке |
| GET | `/proxy/preview?url=<яндекс-превью-урл>` | Прокси превью (добавляет токен) |
| GET | `/proxy/full?path=disk:/Фото/img.jpg` | Прокси полного изображения |
| POST | `/upload` | *(нужно добавить)* Загрузка файла на диск |

---

## 8. Архитектурные решения и почему они такие

### Прокси вместо прямых ссылок
Яндекс API возвращает URL вида `https://downloader.disk.yandex.ru/...?token=XXX`. Этот токен в URL — временный и expires. Плюс для превью нужен заголовок OAuth. Поэтому все картинки идут через Flask-прокси.

### Серверный рендеринг (SSR) вместо SPA
Шаблоны рендерятся на сервере — это проще, быстрее для SEO и не требует отдельного фронтенд-стека. При необходимости можно переписать на React/Vue с API-маршрутами `/api/...`.

### Нет кэширования на сервере
Каждый запрос к `app.py` ходит в Яндекс API заново. Для небольшого сайта это нормально. При большой нагрузке стоит добавить `Flask-Caching` или Redis (раздел 10).

### Masonry через CSS `columns`
Сетка в `album.html` использует CSS `columns` — это чистый CSS без JS. Минус: порядок фото идёт сверху вниз по колонкам, а не слева направо по строкам. Если нужен точный порядок — переключись на CSS Grid или JS-библиотеку (Masonry.js).

---

## 9. Docker и деплой

### Полный `Dockerfile`
```dockerfile
FROM python:3.12-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .
EXPOSE 5000
CMD ["gunicorn", "--bind", "0.0.0.0:5000", "--workers", "2", "--timeout", "60", "app:app"]
```

### Полный `docker-compose.yml`
```yaml
services:
  portfolio:
    build: .
    restart: unless-stopped
    ports:
      - "5000:5000"
    environment:
      - YANDEX_TOKEN=AgAAAAAxxxxx
      - SITE_TITLE=Моё Портфолио
      - SITE_AUTHOR=Иван Иванов
      - ALBUM_PATHS=/Фото/Свадьба,/Фото/Природа
      # - UPLOAD_PASSWORD=секретный_пароль   # раскомментируй если нужна загрузка
```

### Команды

```bash
# Первый запуск / после изменения кода
docker compose up -d --build

# После изменения только docker-compose.yml (переменные окружения)
docker compose down && docker compose up -d

# Логи в реальном времени
docker compose logs -f

# Зайти внутрь контейнера для отладки
docker compose exec portfolio bash

# Посмотреть запущенные контейнеры
docker ps

# Остановить
docker compose down
```

### Nginx как обратный прокси (рекомендуется для продакшена)

Если хочешь HTTPS и красивый домен, добавь Nginx:

```yaml
# docker-compose.yml
services:
  portfolio:
    build: .
    restart: unless-stopped
    expose:
      - "5000"       # не пробрасываем наружу — только через nginx

  nginx:
    image: nginx:alpine
    restart: unless-stopped
    ports:
      - "80:80"
      - "443:443"
    volumes:
      - ./nginx.conf:/etc/nginx/conf.d/default.conf
      - /etc/letsencrypt:/etc/letsencrypt:ro  # SSL сертификаты
```

```nginx
# nginx.conf
server {
    listen 80;
    server_name твой-домен.ru;
    return 301 https://$host$request_uri;
}

server {
    listen 443 ssl;
    server_name твой-домен.ru;

    ssl_certificate     /etc/letsencrypt/live/твой-домен.ru/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/твой-домен.ru/privkey.pem;

    client_max_body_size 100M;   # для загрузки больших фото

    location / {
        proxy_pass         http://portfolio:5000;
        proxy_set_header   Host $host;
        proxy_set_header   X-Real-IP $remote_addr;
        proxy_buffering    off;   # важно для стриминга картинок
    }
}
```

---

## 10. Идеи для дальнейшего развития

| Функция | Сложность | Что потребуется |
|---|---|---|
| Кэширование ответов API | ★☆☆ | `Flask-Caching` + `redis` в docker-compose |
| Авторизация по паролю | ★☆☆ | `flask-login` или простая сессия Flask |
| Метаданные EXIF (камера, выдержка) | ★★☆ | `piexif` или `Pillow`, читать из загруженного файла |
| Пагинация больших альбомов | ★★☆ | `offset` параметр в `yd_list_folder` + кнопка «Загрузить ещё» |
| Поиск по названию | ★★☆ | JS-фильтрация по `IMAGES` массиву или новый API-маршрут |
| Сортировка (по дате/имени) | ★☆☆ | `sorted(images, key=lambda x: x['created'])` в маршруте |
| Вынести CSS/JS в static/ | ★☆☆ | Создать `static/style.css`, подключить через `url_for('static', ...)` |
| Водяной знак на фото | ★★☆ | `Pillow` в `/proxy/full`, наложить PNG-лого |
| Адаптивный просмотрщик (PWA) | ★★★ | Service Worker, manifest.json |
| Редактор метаданных альбомов | ★★★ | JSON-файл настроек на диске или SQLite |

---

*Документация написана для версии проекта с `app.py`, `base.html`, `index.html`, `album.html`. При добавлении новых файлов — дополняй этот документ.*
