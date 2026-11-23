# Берём готовый образ с Python 3.11
FROM python:3.11-slim

# Рабочая папка внутри контейнера
WORKDIR /app

# Сначала копируем список библиотек и ставим их
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Потом копируем сам код и демо-данные
COPY analyzer.py app.py ./
COPY data/sample.csv data/

# Streamlit работает на порту 8501
EXPOSE 8501

# Команда, которая запускается при старте контейнера
CMD ["streamlit", "run", "app.py", "--server.address=0.0.0.0", "--browser.gatherUsageStats=false"]
