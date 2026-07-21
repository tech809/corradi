# Terraform — infraestructura AWS de CORRADI-BOT

Provisiona una **EC2 t4g.small** (ARM, Ubuntu 24.04) con Docker + Compose ya instalados,
en la VPC por defecto (sin NAT Gateway → sin coste extra), con IP elástica estable y un
security group que solo abre SSH (restringido a tu IP) y, opcionalmente, la API.

El despliegue de la app es tu `docker-compose.yml`: Postgres+pgvector, Redis, API y bot.

## Requisitos (en tu máquina)

- **Terraform** ≥ 1.5 (`brew install terraform`).
- **AWS CLI** configurado con credenciales (`aws configure`) de un IAM user con permisos
  EC2/VPC. Terraform usa esas credenciales.
- Una **clave SSH** (`ssh-keygen -t ed25519`). Por defecto se sube `~/.ssh/id_ed25519.pub`.

## Uso

```bash
cd terraform
cp terraform.tfvars.example terraform.tfvars
#  -> edita ssh_allowed_cidr con TU IP/32 (mira https://ifconfig.me)

terraform init
terraform plan
terraform apply        # crea la instancia; imprime la IP y los próximos pasos
```

Tras el `apply` (espera ~2 min al bootstrap):

```bash
# Sube el código y el .env (los secretos NO van en Terraform)
rsync -av --exclude .git --exclude .venv --exclude erasmusbot ../ ubuntu@<IP>:/opt/corradi/
scp ../.env ubuntu@<IP>:/opt/corradi/.env

# Arranca todo
ssh ubuntu@<IP> 'cd /opt/corradi && make up'
ssh ubuntu@<IP> 'cd /opt/corradi && make logs'
```

## Coste

t4g.small: **gratis hasta 31-dic-2026** (free trial AWS, 750 h/mes) y ~17-19 €/mes después.
EBS gp3 30 GB ~2,5 €/mes. Sin NAT Gateway. La IP elástica es gratis mientras esté asociada.

## Resumen diario y semanal (cron)

Por SSH, añade los dos crons en la instancia:
```bash
(crontab -l 2>/dev/null; \
 echo "0 20 * * * cd /opt/corradi && docker compose run --rm bot python -m app.scheduler.daily_summary"; \
 echo "30 20 * * 0 cd /opt/corradi && docker compose run --rm bot python -m app.scheduler.weekly_summary" \
) | crontab -
```
(o usa EventBridge Scheduler + una tarea, como evolución).

## Destruir

```bash
terraform destroy
```

## Seguridad / notas

- **Pon tu IP en `ssh_allowed_cidr`** (`/32`). 0.0.0.0/0 deja SSH abierto al mundo.
- La **API (8000) está cerrada** por defecto (no tiene auth). Accede por túnel:
  `ssh -L 8000:localhost:8000 ubuntu@<IP>` y abre http://localhost:8000.
- El **state de Terraform** puede contener metadatos sensibles: no lo subas a git
  (`.gitignore` ya lo excluye). Para equipo, usa un backend remoto (S3 + DynamoDB lock).
- Los secretos (`GEMINI_API_KEY`, `TELEGRAM_BOT_TOKEN`) viven solo en el `.env` de la
  instancia, nunca en Terraform.
