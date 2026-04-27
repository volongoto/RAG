ARG PYTHON_BASE_IMAGE=python:3.12

FROM ${PYTHON_BASE_IMAGE}

WORKDIR /app

RUN apt-get update \
    && apt-get install -y --no-install-recommends libreoffice-writer \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt -i https://pypi.tuna.tsinghua.edu.cn/simple

COPY . .

EXPOSE 29099

CMD ["python", "app.py", "--env=docker"]
