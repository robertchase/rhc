.PHONY: bash init test

DOCKER_IMAGE := rhc/python
BASE := $(HOME)/git

BASE_DOCKER := docker run -it --rm -v=$(BASE):/opt/git -w /opt/git/rhc -e PYTHONPATH=/opt/git/ergaleia:/opt/git/fsm:. -e MYSQL_HOST=mysql --net test --name rhc $(DOCKER_IMAGE)

bash:
	$(BASE_DOCKER) /bin/bash

test:
	$(BASE_DOCKER) pytest tests

init:
	docker build --rm -t $(DOCKER_IMAGE) .
