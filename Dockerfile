FROM python:3.13

WORKDIR /

COPY . .

RUN pip install -r requirements.txt

EXPOSE 8080 
CMD ["waitress-serve", "main:app"]
