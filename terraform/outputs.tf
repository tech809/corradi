output "public_ip" {
  description = "IP pública de la instancia"
  value       = local.public_ip
}

output "instance_id" {
  value = aws_instance.this.id
}

output "ssh_command" {
  description = "Comando para conectarte por SSH"
  value       = "ssh ubuntu@${local.public_ip}"
}

output "next_steps" {
  description = "Qué hacer tras el apply"
  value       = <<-EOT
    1) Espera ~2 min a que termine el bootstrap (Docker se instala vía user_data).
    2) Copia el código y el .env a la instancia:
         rsync -av --exclude .git --exclude .venv --exclude erasmusbot ./ ubuntu@${local.public_ip}:/opt/corradi/
         scp .env ubuntu@${local.public_ip}:/opt/corradi/.env
       (o, si usaste repo_url, solo necesitas subir el .env)
    3) Arranca:
         ssh ubuntu@${local.public_ip} 'cd /opt/corradi && make up'
    4) Logs:  ssh ubuntu@${local.public_ip} 'cd /opt/corradi && make logs'
  EOT
}
