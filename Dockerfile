FROM python:3.11.6

WORKDIR /app

COPY requirements.txt /app/
RUN pip install -r requirements.txt
RUN pip install uvicorn[standard]

COPY . /app/

CMD ["uvicorn", "backend.asgi:application", "--host", "0.0.0.0", "--port", "8000"]
