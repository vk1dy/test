import yadisk
from flask import Flask, render_template_string

app = Flask(__name__)
# отредачил в вс код
# Вставь свой токен сюда (позже вынесем в переменные окружения)
TOKEN = "y0__wgBENnOvJIEGMzDQSCLi6uxF3nqIc1SAqeyI1L_hI5LrJ2uM_Dy"
y = yadisk.YaDisk(token=TOKEN)

# HTML-шаблон прямо в коде для быстрого теста
HTML_TEMPLATE = """
<!DOCTYPE html>
<html>
<head>
    <title>Мой Яндекс Диск Портфолио</title>
    <style>
        body { font-family: sans-serif; background: #121212; color: white; text-align: center; }
        .gallery { display: grid; grid-template-columns: repeat(auto-fill, minmax(250px, 1fr)); gap: 15px; padding: 20px; }
        img { width: 100%; border-radius: 10px; transition: 0.3s; }
        img:hover { transform: scale(1.05); }
    </style>
</head>
<body>
    <h1>Фото из папки /Portfolio</h1>
    <div class="gallery">
        {% for url in photos %}
            <img src="{{ url }}" alt="Photo">
        {% endfor %}
    </div>
</body>
</html>
"""

@app.route('/')
def index():
    try:
        # Проверяем, существует ли папка Portfolio на Диске
        if not y.exists("/Portfolio"):
            return "Создайте папку 'Portfolio' на Яндекс Диске и загрузите туда фото."
        
        photos = []
        for item in y.listdir("/Portfolio"):
    	    if item.type == "file":
                # Нам нужна именно прямая ссылка на скачивание, а не на страницу просмотра
                direct_url = y.get_download_link(item.path)
                photos.append(direct_url)
        
        return render_template_string(HTML_TEMPLATE, photos=photos)
    except Exception as e:
        return f"Ошибка: {e}"

if __name__ == "__main__":
    app.run(host='0.0.0.0', port=5000)
