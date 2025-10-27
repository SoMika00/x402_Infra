SHELL := /bin/bash

.PHONY: up down logs build test run

up:
	docker compose up --build -d

down:
	docker compose down -v

logs:
	docker compose logs -f --tail=200 api

build:
	docker compose build

run:
	uvicorn app.main:app --reload --host 0.0.0.0 --port 8080

test:
	pytest -q
