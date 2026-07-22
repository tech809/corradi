variable "region" {
  description = "Región de AWS"
  type        = string
  default     = "eu-west-1" # Irlanda
}

variable "project_name" {
  description = "Nombre base para recursos y tags"
  type        = string
  default     = "corradi"
}

variable "instance_type" {
  description = "Tipo de EC2 (ARM/Graviton; t4g.small tiene free trial hasta 31-dic-2026)"
  type        = string
  default     = "t4g.small"
}

variable "root_volume_gb" {
  description = "Tamaño del disco EBS gp3 (GB)"
  type        = number
  default     = 30
}

variable "public_key_path" {
  description = "Ruta a tu clave pública SSH (se sube como key pair a AWS)"
  type        = string
  default     = "~/.ssh/id_ed25519.pub"
}

variable "ssh_allowed_cidr" {
  description = "CIDR autorizado a SSH. ¡Pon tu IP/32! (ej. 81.2.3.4/32). 0.0.0.0/0 deja SSH abierto al mundo."
  type        = string
  default     = "0.0.0.0/0"
}

variable "expose_api" {
  description = "Abrir el puerto 8000 (API FastAPI) a internet. La API no tiene auth: déjalo en false y accede por túnel SSH salvo que sepas lo que haces."
  type        = bool
  default     = false
}

variable "api_allowed_cidr" {
  description = "CIDR autorizado a la API si expose_api = true"
  type        = string
  default     = "0.0.0.0/0"
}

variable "expose_web" {
  description = "Abrir 80/443 para el mapa público servido por Caddy (HTTPS automático). Caddy solo deja pasar las rutas de lectura del mapa; la API cruda NO queda expuesta."
  type        = bool
  default     = false
}

variable "repo_url" {
  description = "URL git del repo a clonar en /opt/corradi durante el arranque (opcional; si vacío, copias el código por scp)"
  type        = string
  default     = ""
}

variable "use_elastic_ip" {
  description = "Asignar una IP elástica estable (gratis mientras esté asociada a una instancia en marcha)"
  type        = bool
  default     = true
}

variable "ssm_client_user" {
  description = "Usuario IAM al que dar permisos de cliente SSM (conectarse a la instancia sin abrir el puerto 22). Vacío = no se crea la política."
  type        = string
  default     = ""
}
