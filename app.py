import os
import requests
import logging
from flask import Flask, render_template, jsonify, request, Response, abort
from functools import lru_cache
import time

app = Flask(__name__)

# ─── Config ───────────────────────────────────────────────────────────────────
YANDEX_TOKEN = os.environ.get("YANDEX_TOKEN", "")
YANDEX_API   = "https://cloud-api.yandex.net/v1/disk/resources"
SITE_TITLE   = os.environ.get("SITE_TITLE", "Portfolio")
SITE_AUTHOR  = os.environ.get("SITE_AUTHOR", "")
# Comma-separated list of Yandex Disk folders to expose as albums
# Example: "/Photos/Wedding,/Photos/Travel"
ALBUM_PATHS  = [p.strip() for p in os.environ.get("ALBUM_PATHS", "/").split(",") if p.strip()]

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".gif", ".webp", ".heic", ".tiff"}

# ─── Yandex Disk helpers ──────────────────────────────────────────────────────

def yd_headers():
    return {"Authorization": f"OAuth {YANDEX_TOKEN}"}


def yd_list_folder(path: str, limit: int = 200) -> list[dict]:
    """Return list of items in a Yandex Disk folder."""
    params = {
        "path": path,
        "limit": limit,
        "fields": "_embedded.items.name,_embedded.items.type,_embedded.items.mime_type,"
                  "_embedded.items.preview,_embedded.items.sizes,_embedded.items.path,"
                  "_embedded.items.created",
        "preview_size": "XXXL",
        "preview_crop": "false",
    }
    resp = requests.get(YANDEX_API, headers=yd_headers(), params=params, timeout=15)
    if resp.status_code == 404:
        return []
    resp.raise_for_status()
    items = resp.json().get("_embedded", {}).get("items", [])
    return items

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

# Описание для hero (опционально)
HERO_DESCRIPTION = os.environ.get(
    "HERO_DESCRIPTION",
    "Фотографии, которые рассказывают истории. Выберите раздел, чтобы погрузиться в работы."
)

# Контактный email (опционально)
CONTACT_EMAIL = os.environ.get("CONTACT_EMAIL", "")

def is_image(item: dict) -> bool:
    name = item.get("name", "").lower()
    mime = item.get("mime_type", "")
    ext  = os.path.splitext(name)[1]
    return ext in IMAGE_EXTENSIONS or mime.startswith("image/")


def get_download_url(path: str) -> str:
    """Get a temporary direct download URL for a file."""
    resp = requests.get(
        f"{YANDEX_API}/download",
        headers=yd_headers(),
        params={"path": path},
        timeout=10,
    )
    resp.raise_for_status()
    return resp.json()["href"]


# ─── Routes ───────────────────────────────────────────────────────────────────
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

def index():
    albums = []
    for folder_path in ALBUM_PATHS:
        try:
            items = yd_list_folder(folder_path)
            images = [i for i in items if is_image(i)]
            # Check for sub-folders (treat them as sub-albums on main page)
            folders = [i for i in items if i.get("type") == "dir"]

            album_name = os.path.basename(folder_path.rstrip("/")) or SITE_TITLE
            cover = images[0].get("preview") if images else None

            albums.append({
                "name": album_name,
                "path": folder_path,
                "cover": cover,
                "count": len(images),
                "has_subfolders": len(folders) > 0,
            })
        except Exception as e:
            logger.error(f"Failed to load {folder_path}: {e}")

    return render_template(
        "index.html",
        albums=albums,
        site_title=SITE_TITLE,
        site_author=SITE_AUTHOR,
        single_album=len(ALBUM_PATHS) == 1,
    )


@app.route("/album")
def album():
    path = request.args.get("path", "/")
    try:
        items = yd_list_folder(path, limit=500)
        images = [
            {
                "name": i["name"],
                "path": i["path"],
                "preview": i.get("preview", ""),
                "created": i.get("created", ""),
            }
            for i in items if is_image(i)
        ]
        subfolders = [
            {"name": i["name"], "path": i["path"]}
            for i in items if i.get("type") == "dir"
        ]
        album_name = os.path.basename(path.rstrip("/")) or SITE_TITLE
    except Exception as e:
        logger.error(f"Failed to load album {path}: {e}")
        abort(500)

    return render_template(
        "album.html",
        images=images,
        subfolders=subfolders,
        album_name=album_name,
        album_path=path,
        site_title=SITE_TITLE,
        site_author=SITE_AUTHOR,
    )


@app.route("/api/albums")
def api_albums():
    """JSON list of top-level albums."""
    albums = []
    for folder_path in ALBUM_PATHS:
        try:
            items = yd_list_folder(folder_path)
            images = [i for i in items if is_image(i)]
            folders = [i for i in items if i.get("type") == "dir"]
            albums.append({
                "name": os.path.basename(folder_path.rstrip("/")) or "Root",
                "path": folder_path,
                "count": len(images),
                "cover_preview": images[0].get("preview") if images else None,
                "subfolders": [{"name": f["name"], "path": f["path"]} for f in folders],
            })
        except Exception as e:
            logger.error(e)
    return jsonify(albums)


@app.route("/api/images")
def api_images():
    """JSON list of images in a folder path."""
    path = request.args.get("path", "/")
    try:
        items = yd_list_folder(path, limit=500)
        images = [
            {
                "name": i["name"],
                "path": i["path"],
                "preview": i.get("preview", ""),
                "created": i.get("created", ""),
            }
            for i in items if is_image(i)
        ]
        return jsonify({"images": images, "total": len(images)})
    except Exception as e:
        logger.error(e)
        return jsonify({"error": str(e)}), 500


@app.route("/proxy/preview")
def proxy_preview():
    """Proxy Yandex preview images to avoid CORS / auth issues in browser."""
    url = request.args.get("url")
    if not url or "downloader.disk.yandex" not in url and "preview" not in url:
        abort(400)
    try:
        resp = requests.get(url, headers=yd_headers(), timeout=15, stream=True)
        resp.raise_for_status()
        return Response(
            resp.iter_content(chunk_size=8192),
            content_type=resp.headers.get("content-type", "image/jpeg"),
            headers={"Cache-Control": "public, max-age=3600"},
        )
    except Exception as e:
        logger.error(f"Preview proxy error: {e}")
        abort(502)


@app.route("/proxy/full")
def proxy_full():
    """Proxy full-size images via a temporary Yandex download link."""
    path = request.args.get("path")
    if not path:
        abort(400)
    try:
        url = get_download_url(path)
        resp = requests.get(url, timeout=30, stream=True)
        resp.raise_for_status()
        return Response(
            resp.iter_content(chunk_size=65536),
            content_type=resp.headers.get("content-type", "image/jpeg"),
            headers={"Cache-Control": "public, max-age=600"},
        )
    except Exception as e:
        logger.error(f"Full image proxy error: {e}")
        abort(502)


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=False)
