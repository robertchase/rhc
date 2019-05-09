.PHONY: bash init test

DOCKER_IMAGE := rhc/python
BASE := $(HOME)/git/rhc

BASE_DOCKER := docker run -it --rm -v=$(BASE):/opt/git/rhc -w /opt/git/rhc -e MYSQL_HOST=mysql --net test --name rhc $(DOCKER_IMAGE)

bash:
	$(BASE_DOCKER) /bin/bash

test:
	$(BASE_DOCKER) pytest tests

init:
	docker build --rm -t $(DOCKER_IMAGE) .
