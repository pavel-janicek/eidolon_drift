# docker/Dockerfile
FROM python:3.11-slim
RUN apt-get update && apt-get install -y openssh-server && rm -rf /var/lib/apt/lists/*
RUN mkdir /var/run/sshd
WORKDIR /app
COPY . /app
# create a user 'rescue' and set shell to run the game
RUN useradd -m rescue && echo "rescue:rescue" | chpasswd
# set rescue's shell to python main (this is simplified; better to use entrypoint)
RUN ln -s /usr/bin/python3 /usr/bin/python
EXPOSE 22
CMD ["bash", "-lc", "python3 /app/main.py"]
