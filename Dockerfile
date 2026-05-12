FROM python:3.9-slim

WORKDIR /app

# Устанавливаем зависимости
RUN pip install --no-cache-dir flask requests

# Копируем все файлы (app.py, templates/, etc.)
COPY . .

# Переменные по умолчанию (их можно будет переопределить при запуске)
ENV YANDEX_TOKEN="y0__wgBENnOvJIEGMzDQSCLi6uxF3nqIc1SAqeyI1L_hI5LrJ2uM_Dy"
ENV ALBUM_PATHS="/"

EXPOSE 5000

CMD ["python", "app.py"]