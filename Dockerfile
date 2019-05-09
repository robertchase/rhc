# base python image
FROM ubuntu:16.04
RUN apt-get update && apt-get upgrade -y && apt-get install -y python python-pip python-dev libffi-dev libssl-dev mysql-client-5.7 vim git man screen curl unzip telnet tree

RUN pip install --upgrade pip
RUN pip install PyMySQL pytest
RUN rm /bin/sh && ln -s /bin/bash /bin/sh
