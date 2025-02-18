FROM python:3.13

WORKDIR /

COPY . .

COPY requirements.txt .
COPY app.py .

RUN pip install -r requirements.txt

EXPOSE 5002 
ENTRYPOINT ["python"]
CMD ["app.py"]
