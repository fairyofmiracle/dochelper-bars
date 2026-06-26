FROM python:3.11-slim

WORKDIR /app

# CPU-only torch
RUN pip install --no-cache-dir torch --index-url https://download.pytorch.org/whl/cpu

COPY requirements.txt .
RUN grep -v "^--extra-index-url" requirements.txt | grep -v "^torch" > /tmp/req.txt \
    && pip install --no-cache-dir -r /tmp/req.txt

COPY . .

EXPOSE 8026
CMD ["python", "main.py"]
