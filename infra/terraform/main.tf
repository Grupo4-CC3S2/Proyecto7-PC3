terraform {
  required_providers {
    docker = {
      source  = "kreuzwerker/docker"
      version = "~> 3.3.0"
    }
  }
}

# Imagen de RabbitMQ (con la UI de gestión)
resource "docker_image" "rabbitmq" {
  name         = "rabbitmq:3-management"
  keep_locally = false
}

# Imagen de Redis
resource "docker_image" "redis" {
  name         = "redis:latest"
  keep_locally = false
}

# Contenedor de RabbitMQ
resource "docker_container" "rabbitmq" {
  name  = "chaos-broker"
  image = docker_image.rabbitmq.image_id
  ports {
    internal = 5672 # puerto para la app
    external = 5671
  }
  ports {
    internal = 15672 # puerto para la UI web
    external = 15673
  }
}

# Contenedor de Redis
resource "docker_container" "redis" {
  name  = "chaos-db"
  image = docker_image.redis.image_id
  ports {
    internal = 6379
    external = 6379
  }
}