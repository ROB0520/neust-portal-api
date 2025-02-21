FROM python:3.13

WORKDIR /

COPY . .

RUN pip install -r requirements.txt

EXPOSE 5002 
CMD ["waitress-serve", "main:app"]
