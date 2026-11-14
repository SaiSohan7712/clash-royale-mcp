FROM python:3.12-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt uvicorn
COPY src ./src
ENV MCP_TRANSPORT=http
CMD ["python", "src/server.py"]
