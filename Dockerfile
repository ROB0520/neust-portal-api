# syntax=docker/dockerfile:1.4
FROM python:3.13 AS builder

WORKDIR /

COPY requirements.txt .
COPY app.py .

RUN pip3 install -r requirements.txt

ENTRYPOINT ["python3"]
CMD ["app.py"]
