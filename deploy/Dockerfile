# 备用部署方式：平台自带的 Streamlit 环境装不上依赖或版本太旧时，改用 Docker 方式部署。
# 魔搭创空间选 Docker 类型时，把这个文件复制到仓库根目录；平台要求监听 7860 端口。
FROM python:3.11-slim

WORKDIR /app
ARG PIP_INDEX_URL=https://mirrors.aliyun.com/pypi/simple/
COPY requirements.txt .
RUN pip install --no-cache-dir -i ${PIP_INDEX_URL} -r requirements.txt

COPY app.py ./
COPY askdata ./askdata
COPY data/olist ./data/olist
COPY .streamlit ./.streamlit

EXPOSE 7860
CMD ["streamlit", "run", "app.py", "--server.port=7860", "--server.address=0.0.0.0", "--server.headless=true"]
