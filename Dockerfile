# start by pulling the python image
FROM python:3.12-rc-alpine

CMD ["/hello"]

# copy the requirements file into the image
COPY ./requirements.txt /app/requirements.txt

# switch working directory
WORKDIR /app

# set environment variables
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

RUN apk update && apk add python3-dev musl-dev

# install the dependencies and packages in the requirements file
RUN pip install --upgrade pip
RUN export LDFLAGS="-L/usr/local/opt/openssl/lib"
RUN pip install -r /app/requirements.txt

# copy every content from the local file to the image
COPY . /app

EXPOSE 5000

# configure the container to run in an executed manner
ENTRYPOINT [ "python" ]

CMD ["view.py" ]