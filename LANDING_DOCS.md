# 🎨 Главный экран (Landing Page) — Инструкция

Документация по шаблону `landing.html` — как подключить, настроить
и расширять лендинг с разделами портфолио.

---

## Содержание

1. [Что такое landing.html и как он отличается от index.html](#1-что-такое-landinghtml)
2. [Как подключить лендинг в app.py](#2-как-подключить-лендинг-в-apppy)
3. [Структура данных — что передаётся в шаблон](#3-структура-данных)
4. [Настройка разделов через docker-compose.yml](#4-настройка-разделов)
5. [Добавить секцию «О себе»](#5-добавить-секцию-о-себе)
6. [Как изменить раскладку карточек](#6-как-изменить-раскладку-карточек)
7. [Как изменить визуал (цвета, шрифты, анимации)](#7-визуальная-кастомизация)
8. [Полный app.py с лендингом](#8-полный-apppy-с-лендингом)

---

## 1. Что такое landing.html

`landing.html` — это **отдельный главный экран** перед сеткой альбомов.
В отличие от `index.html` (просто сетка альбомов), лендинг содержит:

```
landing.html                     index.html
─────────────────────────        ─────────────────
• Hero с именем автора           • Просто карточки альбомов
• Разделы как крупные карточки
• Секция «О себе»
• Кастомный курсор
• Scroll-анимации
• Footer с контактом
```

**Маршрутизация после добавления лендинга:**

```
/           → landing.html  (главный экран с разделами)
/portfolio  → index.html    (сетка альбомов, если нужна)
/album?path=...  → album.html   (конкретный альбом)
```

---

## 2. Как подключить лендинг в app.py

Замени маршрут `/` в `app.py`:

```python
# ─── Конфигурация разделов ────────────────────────────────────────────────────
# Разделы задаются в docker-compose.yml как:
# SECTIONS=Свадьбы:/Фото/Свадьбы,Природа:/Фото/Природа,Портреты:/Фото/Портреты
# Формат: "Название:путь_на_диске" через запятую

def parse_sections_config(env_str: str) -> list[dict]:
    """
    Разбирает строку вида "Свадьбы:/Фото/Свадьбы,Природа:/Фото/Природа"
    в список словарей [{"name": "Свадьбы", "path": "/Фото/Свадьбы"}, ...]
    """
    result = []
    if not env_str:
        return result
    for item in env_str.split(","):
        item = item.strip()
        if ":" not in item:
            continue
        name, path = item.split(":", 1)
        result.append({"name": name.strip(), "path": path.strip()})
    return result

SECTIONS_CONFIG = parse_sections_config(os.environ.get("SECTIONS", ""))

# Теги для разделов (опционально, через env)
# SECTION_TAGS=Свадьбы:Wedding,Природа:Nature
def parse_tags(env_str: str) -> dict:
    tags = {}
    for item in (env_str or "").split(","):
        if ":" in item:
            k, v = item.split(":", 1)
            tags[k.strip()] = v.strip()
    return tags

SECTION_TAGS = parse_tags(os.environ.get("SECTION_TAGS", ""))

# Описание для hero (опционально)
HERO_DESCRIPTION = os.environ.get(
    "HERO_DESCRIPTION",
    "Фотографии, которые рассказывают истории. Выберите раздел, чтобы погрузиться в работы."
)

# Контактный email (опционально)
CONTACT_EMAIL = os.environ.get("CONTACT_EMAIL", "")


# ─── Маршрут / (лендинг) ──────────────────────────────────────────────────────
@app.route("/")
def landing():
    sections = []

    for sec in SECTIONS_CONFIG:
        try:
            items = yd_list_folder(sec["path"], limit=100)
            images  = [i for i in items if is_image(i)]
            folders = [i for i in items if i.get("type") == "dir"]

            # Обложка — первое фото в папке
            cover = images[0].get("preview") if images else None

            # Если в папке только подпапки — попробуем взять обложку из первой
            if not cover and folders:
                try:
                    sub_items = yd_list_folder(folders[0]["path"], limit=5)
                    sub_images = [i for i in sub_items if is_image(i)]
                    cover = sub_images[0].get("preview") if sub_images else None
                except Exception:
                    pass

            # Подсчёт фотографий (включая вложенные папки — приблизительно)
            total_count = len(images)
            if folders:
                total_count = f"{total_count}+" if total_count else f"{len(folders)} альбомов"

            sections.append({
                "name":  sec["name"],
                "path":  sec["path"],
                "url":   f"/album?path={sec['path']}",
                "cover": cover,
                "count": total_count,
                "tag":   SECTION_TAGS.get(sec["name"], "Portfolio"),
            })

        except Exception as e:
            logger.error(f"Landing: failed to load section {sec['name']}: {e}")
            # Добавляем раздел без обложки, чтобы он всё равно отображался
            sections.append({
                "name":  sec["name"],
                "path":  sec["path"],
                "url":   f"/album?path={sec['path']}",
                "cover": None,
                "count": 0,
                "tag":   SECTION_TAGS.get(sec["name"], "Portfolio"),
            })

    # Секция "О себе" (опционально, из переменных окружения)
    about_cells = _build_about_cells()

    from datetime import datetime
    return render_template(
        "landing.html",
        sections=sections,
        site_title=SITE_TITLE,
        site_author=SITE_AUTHOR,
        hero_description=HERO_DESCRIPTION,
        contact_email=CONTACT_EMAIL,
        about_cells=about_cells,
        now=datetime.now(),
    )


def _build_about_cells() -> list[dict]:
    """
    Формирует ячейки секции «О себе» из переменных окружения.
    Переменные: ABOUT_1_LABEL, ABOUT_1_VALUE, ABOUT_1_SUB (и 2, 3)
    """
    cells = []
    for i in range(1, 4):
        label = os.environ.get(f"ABOUT_{i}_LABEL", "")
        value = os.environ.get(f"ABOUT_{i}_VALUE", "")
        if label and value:
            cells.append({
                "label": label,
                "value": value,
                "sub":   os.environ.get(f"ABOUT_{i}_SUB", ""),
            })
    return cells


# ─── Маршрут /portfolio — старая главная (опционально оставить) ───────────────
@app.route("/portfolio")
def portfolio():
    """Старая страница index.html со всеми альбомами."""
    albums = []
    for folder_path in ALBUM_PATHS:
        try:
            items  = yd_list_folder(folder_path)
            images = [i for i in items if is_image(i)]
            cover  = images[0].get("preview") if images else None
            albums.append({
                "name":            os.path.basename(folder_path.rstrip("/")) or SITE_TITLE,
                "path":            folder_path,
                "cover":           cover,
                "count":           len(images),
                "has_subfolders":  any(i.get("type") == "dir" for i in items),
            })
        except Exception as e:
            logger.error(f"Portfolio: failed to load {folder_path}: {e}")

    return render_template(
        "index.html",
        albums=albums,
        site_title=SITE_TITLE,
        site_author=SITE_AUTHOR,
        single_album=len(ALBUM_PATHS) == 1,
    )
```

---

## 3. Структура данных

Что передаётся в `landing.html` из `app.py`:

```python
# sections — список разделов
sections = [
    {
        "name":  "Свадьбы",                          # заголовок карточки
        "path":  "/Фото/Свадьбы",                    # путь на Яндекс Диске
        "url":   "/album?path=/Фото/Свадьбы",        # ссылка при клике
        "cover": "https://downloader.disk.yandex...", # превью обложки
        "count": "42+",                              # кол-во фото
        "tag":   "Wedding",                          # подпись над заголовком
    },
    ...
]

# about_cells — ячейки секции "О себе" (опционально)
about_cells = [
    {"label": "Локация", "value": "Москва", "sub": "Выезды по России"},
    {"label": "Опыт",    "value": "7 лет",  "sub": "Более 200 съёмок"},
    {"label": "Контакт", "value": "ivan@example.com", "sub": ""},
]
```

---

## 4. Настройка разделов

Всё через `docker-compose.yml`:

```yaml
environment:
  - YANDEX_TOKEN=AgAAAAAxxxxx
  - SITE_TITLE=Ivan Photo
  - SITE_AUTHOR=Иван Иванов

  # Разделы: "Название:путь_на_диске" через запятую
  - SECTIONS=Свадьбы:/Фото/Свадьбы,Репортаж:/Фото/Репортаж,Портреты:/Фото/Портреты,Природа:/Фото/Природа

  # Теги под названием раздела (опционально)
  - SECTION_TAGS=Свадьбы:Wedding,Репортаж:Reportage,Портреты:Portrait,Природа:Nature

  # Текст в hero
  - HERO_DESCRIPTION=Свадебная и репортажная фотография. Москва и вся Россия.

  # Контактный email в footer
  - CONTACT_EMAIL=ivan@example.com

  # Секция "О себе" (до 3 ячеек)
  - ABOUT_1_LABEL=Локация
  - ABOUT_1_VALUE=Москва
  - ABOUT_1_SUB=Выезды по всей России

  - ABOUT_2_LABEL=Опыт
  - ABOUT_2_VALUE=7 лет
  - ABOUT_2_SUB=Более 200 съёмок

  - ABOUT_3_LABEL=Контакт
  - ABOUT_3_VALUE=ivan@example.com
  - ABOUT_3_SUB=Ответ в течение дня
```

---

## 5. Добавить секцию «О себе»

Секция появляется автоматически когда заданы переменные `ABOUT_N_*`.
Без них — секция не рендерится совсем (см. Jinja2 условие в шаблоне):

```html
{% if about_cells is defined and about_cells %}
<div id="about" class="about-strip"> ... </div>
{% endif %}
```

Чтобы добавить **фото автора** рядом с текстом — измени шаблон:

```html
<!-- landing.html, в секцию about_strip добавь колонку с фото: -->
<div id="about" class="about-strip" style="grid-template-columns: 300px 1px 1fr 1px 1fr 1px 1fr;">
  <div class="about-cell">
    <img src="/proxy/full?path={{ author_photo_path }}"
         style="width:100%; aspect-ratio:3/4; object-fit:cover; filter:grayscale(0.3);" />
  </div>
  <div class="about-divider-v"></div>
  <!-- остальные ячейки -->
</div>
```

И в `app.py` добавь переменную `author_photo_path`:
```python
return render_template(
    "landing.html",
    ...
    author_photo_path=os.environ.get("AUTHOR_PHOTO_PATH", ""),
)
```

---

## 6. Как изменить раскладку карточек

В `landing.html` найди блок с `nth-child` — это CSS-правила для колонок:

```css
/* Текущая раскладка (сумма span = 12 в каждой строке): */
.section-card:nth-child(1) { grid-column: span 7; aspect-ratio: 16/9; }
.section-card:nth-child(2) { grid-column: span 5; aspect-ratio: 4/5;  }
.section-card:nth-child(3) { grid-column: span 4; aspect-ratio: 4/5;  }
.section-card:nth-child(4) { grid-column: span 4; aspect-ratio: 4/5;  }
.section-card:nth-child(5) { grid-column: span 4; aspect-ratio: 4/5;  }
```

**Равная сетка 3 колонки:**
```css
.section-card:nth-child(n) { grid-column: span 4; aspect-ratio: 4/3; }
```

**Две большие + одна маленькая:**
```css
.section-card:nth-child(1) { grid-column: span 8; aspect-ratio: 16/9; }
.section-card:nth-child(2) { grid-column: span 4; aspect-ratio: 4/3;  }
.section-card:nth-child(3) { grid-column: span 4; aspect-ratio: 4/3;  }
.section-card:nth-child(4) { grid-column: span 4; aspect-ratio: 4/3;  }
.section-card:nth-child(5) { grid-column: span 4; aspect-ratio: 4/3;  }
```

**Полная ширина для каждой:**
```css
.section-card:nth-child(n) { grid-column: span 12; aspect-ratio: 21/9; }
```

---

## 7. Визуальная кастомизация

### Изменить цвета

В `landing.html`, раздел `:root`:

```css
:root {
  --bg:   #0b0b0b;   /* фон страницы */
  --ink:  #e9e4dc;   /* основной текст */
  --gold: #c9a97f;   /* акцентный цвет (заголовки разделов, линии) */
  --teal: #7fa89d;   /* второй акцент */
  --muted: rgba(233,228,220,0.38);  /* приглушённый текст */
}
```

### Изменить шрифты

```html
<!-- Заменить в <head>: -->
<link href="https://fonts.googleapis.com/css2?family=Playfair+Display:ital,wght@0,400;1,400&family=DM+Sans:wght@300;400&display=swap" rel="stylesheet">
```
```css
:root {
  --f-disp: 'Playfair Display', serif;
  --f-body: 'DM Sans', sans-serif;
}
```

### Отключить кастомный курсор

В `landing.html` найди и удали:
```html
<!-- Удали эти строки -->
<div class="cursor" id="cursor-dot" ><div class="cursor-dot"></div></div>
<div class="cursor" id="cursor-ring"><div class="cursor-ring"></div></div>
```
```css
/* И в CSS замени: */
body { cursor: auto; }   /* вместо cursor: none */
```

### Изменить скорость анимации карточек

```css
.section-card-bg {
  transition: transform 0.9s var(--ease);  /* ← уменьши для быстрее */
}
.reveal {
  transition: opacity 0.9s var(--ease), transform 0.9s var(--ease);
}
```

### Убрать зернистый фон (grain overlay)

Найди и удали:
```css
body::before { ... }   /* весь этот блок */
```

---

## 8. Полный app.py с лендингом

Если хочешь начать с нуля — вот минимальный `app.py` который запускает
только лендинг (без index.html):

```python
import os, requests, logging
from flask import Flask, render_template, request, Response, abort, jsonify
from datetime import datetime

app = Flask(__name__)
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

YANDEX_TOKEN      = os.environ.get("YANDEX_TOKEN", "")
YANDEX_API        = "https://cloud-api.yandex.net/v1/disk/resources"
SITE_TITLE        = os.environ.get("SITE_TITLE", "Portfolio")
SITE_AUTHOR       = os.environ.get("SITE_AUTHOR", "")
HERO_DESCRIPTION  = os.environ.get("HERO_DESCRIPTION", "")
CONTACT_EMAIL     = os.environ.get("CONTACT_EMAIL", "")
IMAGE_EXTENSIONS  = {".jpg", ".jpeg", ".png", ".gif", ".webp", ".heic", ".tiff"}

def yd_headers():
    return {"Authorization": f"OAuth {YANDEX_TOKEN}"}

def yd_list_folder(path, limit=200):
    params = {
        "path": path, "limit": limit,
        "fields": "_embedded.items.name,_embedded.items.type,"
                  "_embedded.items.mime_type,_embedded.items.preview,"
                  "_embedded.items.path,_embedded.items.created",
        "preview_size": "XL",
    }
    r = requests.get(YANDEX_API, headers=yd_headers(), params=params, timeout=15)
    if r.status_code == 404: return []
    r.raise_for_status()
    return r.json().get("_embedded", {}).get("items", [])

def is_image(item):
    ext = os.path.splitext(item.get("name","").lower())[1]
    return ext in IMAGE_EXTENSIONS or item.get("mime_type","").startswith("image/")

def parse_sections_config(s):
    result = []
    for item in (s or "").split(","):
        item = item.strip()
        if ":" in item:
            name, path = item.split(":", 1)
            result.append({"name": name.strip(), "path": path.strip()})
    return result

def parse_tags(s):
    tags = {}
    for item in (s or "").split(","):
        if ":" in item:
            k, v = item.split(":", 1)
            tags[k.strip()] = v.strip()
    return tags

SECTIONS_CONFIG = parse_sections_config(os.environ.get("SECTIONS", ""))
SECTION_TAGS    = parse_tags(os.environ.get("SECTION_TAGS", ""))

@app.route("/")
def landing():
    sections = []
    for sec in SECTIONS_CONFIG:
        try:
            items   = yd_list_folder(sec["path"], 100)
            images  = [i for i in items if is_image(i)]
            folders = [i for i in items if i.get("type") == "dir"]
            cover   = images[0].get("preview") if images else None
            if not cover and folders:
                sub = yd_list_folder(folders[0]["path"], 5)
                si  = [i for i in sub if is_image(i)]
                cover = si[0].get("preview") if si else None
            count = len(images) if images else (f"{len(folders)} альбомов" if folders else 0)
        except Exception as e:
            logger.error(e)
            cover, count = None, 0
        sections.append({
            "name": sec["name"], "path": sec["path"],
            "url":  f"/album?path={sec['path']}",
            "cover": cover, "count": count,
            "tag":  SECTION_TAGS.get(sec["name"], "Portfolio"),
        })

    about_cells = [
        {"label": os.environ.get(f"ABOUT_{i}_LABEL",""),
         "value": os.environ.get(f"ABOUT_{i}_VALUE",""),
         "sub":   os.environ.get(f"ABOUT_{i}_SUB","")}
        for i in range(1,4)
        if os.environ.get(f"ABOUT_{i}_LABEL") and os.environ.get(f"ABOUT_{i}_VALUE")
    ]

    return render_template("landing.html",
        sections=sections, site_title=SITE_TITLE, site_author=SITE_AUTHOR,
        hero_description=HERO_DESCRIPTION, contact_email=CONTACT_EMAIL,
        about_cells=about_cells, now=datetime.now())

@app.route("/album")
def album():
    path = request.args.get("path", "/")
    try:
        items    = yd_list_folder(path, 500)
        images   = [{"name":i["name"],"path":i["path"],"preview":i.get("preview",""),"created":i.get("created","")} for i in items if is_image(i)]
        subfolders = [{"name":i["name"],"path":i["path"]} for i in items if i.get("type")=="dir"]
    except Exception as e:
        logger.error(e); abort(500)
    return render_template("album.html",
        images=images, subfolders=subfolders,
        album_name=os.path.basename(path.rstrip("/")) or SITE_TITLE,
        album_path=path, site_title=SITE_TITLE, site_author=SITE_AUTHOR)

@app.route("/proxy/preview")
def proxy_preview():
    url = request.args.get("url")
    if not url: abort(400)
    r = requests.get(url, headers=yd_headers(), timeout=15, stream=True)
    r.raise_for_status()
    return Response(r.iter_content(8192),
        content_type=r.headers.get("content-type","image/jpeg"),
        headers={"Cache-Control":"public, max-age=3600"})

@app.route("/proxy/full")
def proxy_full():
    path = request.args.get("path")
    if not path: abort(400)
    r1 = requests.get(f"{YANDEX_API}/download", headers=yd_headers(), params={"path":path}, timeout=10)
    r1.raise_for_status()
    r2 = requests.get(r1.json()["href"], timeout=30, stream=True)
    r2.raise_for_status()
    return Response(r2.iter_content(65536),
        content_type=r2.headers.get("content-type","image/jpeg"),
        headers={"Cache-Control":"public, max-age=600"})

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=False)
```

---

*После копирования кода из этого файла — перезапусти контейнер:*
```bash
docker compose up -d --build
```
