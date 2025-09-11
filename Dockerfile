# 使用官方 Python 3.9 的精簡版作為基礎映像檔
FROM python:3.9-slim

# 設定容器中的工作目錄
WORKDIR /app

# 將 requirements.txt 複製到工作目錄並安裝所有依賴
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 複製專案中的所有檔案到容器裡
COPY . .

# 設定容器啟動時的指令
CMD gunicorn app:app