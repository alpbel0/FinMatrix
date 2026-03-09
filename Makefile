.PHONY: build up down logs clean test shell help

help:
	@echo "FinMatrix Development Commands"
	@echo "=============================="
	@echo "make build    - Build Docker images"
	@echo "make up       - Start all services"
	@echo "make down     - Stop all services"
	@echo "make logs     - View container logs"
	@echo "make clean    - Remove volumes and clean up"
	@echo "make test     - Run tests"
	@echo "make shell    - Open backend shell"

build:
	docker-compose build

up:
	docker-compose up -d

down:
	docker-compose down

logs:
	docker-compose logs -f

clean:
	docker-compose down -v
	rm -rf chroma_data/

test:
	docker-compose exec api pytest

shell:
	docker-compose exec api /bin/bash