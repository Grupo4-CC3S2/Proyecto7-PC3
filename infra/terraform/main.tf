terraform {
  required_providers {
    docker = {
      source  = "kreuzwerker/docker"
      version = "~> 3.3.0"
    }
  }
}

# Variables para los Puertos
variable "rabbitmq_port_app" {
  description = "Puerto externo para la App de RabbitMQ"
  type        = number
  default     = 5671
}
variable "rabbitmq_port_ui" {
  description = "Puerto externo para la UI de RabbitMQ "
  type        = number
  default     = 15673
}
variable "redis_port" {
  description = "Puerto externo para Redis"
  type        = number
  default     = 6379
}
variable "app_port" {
  description = "Puerto externo para la API (FastAPI)"
  type        = number
  default     = 8000
}

# Creamos una red para los contenedores 
resource "docker_network" "chaos_net" {
  name = "chaos-network"
}

resource "docker_image" "rabbitmq" {
  name         = "rabbitmq:3-management"
  keep_locally = false
}
resource "docker_image" "redis" {
  name         = "redis:latest"
  keep_locally = false
}

resource "docker_image" "worker" {
  name         = "chaos-worker:latest"
  keep_locally = true
}

resource "docker_image" "app" {
  name         = "chaos-app:latest"
  keep_locally = true
}

resource "docker_container" "rabbitmq" {
  name  = "chaos-broker"
  image = docker_image.rabbitmq.image_id
  ports {
    internal = 5672
    external = var.rabbitmq_port_app
  }
  ports {
    internal = 15672
    external = var.rabbitmq_port_ui
  }
  networks_advanced {
    name = docker_network.chaos_net.name
  }
}

resource "docker_container" "redis" {
  name  = "chaos-db"
  image = docker_image.redis.image_id
  ports {
    internal = 6379
    external = var.redis_port
  }
  networks_advanced {
    name = docker_network.chaos_net.name
  }
}

resource "docker_container" "app_container" {
  name  = "chaos-app"
  image = docker_image.app.image_id
  ports {
    internal = 8000
    external = var.app_port
  }
  networks_advanced {
    name = docker_network.chaos_net.name
  }
  # Pasa las variables de entorno a la app
  env = [
    "RABBITMQ_HOST=chaos-broker",
    # Usamos el puerto interno, ya que estamos en la misma red
    "RABBITMQ_PORT=5672"
  ]
  restart = "unless-stopped"

  # Dependeremos de que el broker esté listo
  depends_on = [docker_container.rabbitmq]
}

resource "docker_container" "worker_container" {
  name  = "chaos-worker"
  image = docker_image.worker.image_id

  networks_advanced {
    name = docker_network.chaos_net.name
  }

  # Pasa las variables de entorno al worker
  env = [
    "RABBITMQ_HOST=chaos-broker",
    "RABBITMQ_PORT=5672",
    "REDIS_HOST=chaos-db",
    "REDIS_PORT=6379",
    "CHAOS_RATE=0.7"
  ]
  restart = "on-failure"

  depends_on = [
    docker_container.rabbitmq,
    docker_container.redis
  ]
}