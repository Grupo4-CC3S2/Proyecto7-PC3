PYTHON = python
VENV_DIR = .venv
PIP = $(VENV_DIR)/Scripts/pip
PYTEST = $(VENV_DIR)/Scripts/pytest

.PHONY: all install test lint clean up down run-app run-worker help

all: help

install: requirements.txt
	@echo "Instalando dependencias."
	$(PIP) install -r requirements.txt

test:
	@echo "Ejecutando pruebas unitarias"
	$(PYTHON) -m pytest -v

lint:
	@echo "Lanzando formateador (black)"
	$(PIP) install black
	$(VENV_DIR)/Scripts/black src tests

clean:
	@echo "Limpiando archivos .pyc y __pycache__"
	find . -type f -name "*.pyc" -delete
	find . -type d -name "__pycache__" -exec rm -rf {} +

up:
	@echo "Levantando infraestructura (RabbitMQ, Redis)..."
	cd infra/terraform && terraform apply --auto-approve

run-app:
	@echo "Iniciando la app API"
	$(PYTHON) -m src.app

run-worker:
	@echo "Iniciando el Worker"
	$(PYTHON) -m src.worker

help:
	@echo "Comandos disponibles:"
	@echo "  make install    Instala las dependencias de requirements.txt"
	@echo "  make test       Ejecuta todas las pruebas con pytest"
	@echo "  make lint       Formatea el código con 'black'"
	@echo "  make up         Levanta la infraestructura de Docker (Terraform)"
	@echo "  make down       Destruye la infraestructura de Docker (Terraform)"
	@echo "  make run-app    Ejecuta la API"
	@echo "  make run-worker Ejecuta el Worker"
	@echo "  make clean      Limpia los archivos .pyc"