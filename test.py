import time
import os

# Скрипт будет выводить системную информацию каждую секунду
while True:
    print(f"Пулс Docker... Время: {time.ctime()}")
    print(f"Я работаю внутри контейнера под пользователем: {os.getlogin() if hasattr(os, 'getlogin') else 'root'}")
    time.sleep(5)