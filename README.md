docker build -t my-flask-app .
docker run -p 5000:5000 --env-file .env my-flask-app
