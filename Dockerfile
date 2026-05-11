FROM python:3.9-slim

# Устанавливаем зависимости
RUN pip install flask yadisk requests

WORKDIR /app

# Копируем именно твой новый скрипт
COPY yadisk-portfolio.py .

# Указываем Python запустить именно этот файл
CMD ["python", "yadisk-portfolio.py"]
