# Terraform — infraestructura AWS de CORRADI-BOT

Provisiona una **EC2 t4g.small** (ARM, Ubuntu 24.04) con Docker + Compose ya instalados,
en la VPC por defecto (sin NAT Gateway → sin coste extra), con IP elástica estable, un rol
IAM para **SSM Session Manager** y un security group que en producción **no abre el puerto
22** (el acceso es solo por SSM, ver abajo) y opcionalmente 80/443 para el mapa (Caddy).

El despliegue de la app es tu `docker-compose.yml`: Postgres+pgvector, API, bot y Caddy.

## Requisitos (en tu máquina)

- **Terraform** ≥ 1.5 (`brew install terraform`).
- **AWS CLI** configurado con credenciales (`aws configure`) de un IAM user con permisos
  EC2/VPC/IAM. Terraform usa esas credenciales.
- **`session-manager-plugin`** de AWS (`brew install --cask session-manager-plugin`), para
  poder hacer SSH sobre SSM (ver [Acceso a la instancia](#acceso-a-la-instancia-ssm) más abajo).
- Una **clave SSH** (`ssh-keygen -t ed25519`). Por defecto se sube `~/.ssh/id_ed25519.pub` —
  la usa el propio túnel SSM, no hace falta el puerto 22 abierto en el security group.

## Uso

```bash
cd terraform
cp terraform.tfvars.example terraform.tfvars
#  -> pon ssh_allowed_cidr = ""  (cierra el 22 del todo; el acceso real es por SSM)
#  -> pon ssm_client_user con tu usuario IAM, para que puedas hacer SSM StartSession
#  -> pon expose_web = true si quieres el mapa público (Caddy con HTTPS automático)

terraform init
terraform plan
terraform apply        # crea la instancia; imprime la IP y los próximos pasos
```

Tras el `apply` (espera ~2 min al bootstrap, hasta que el agente SSM registra la instancia):

```bash
# Sube el código y el .env (los secretos NO van en Terraform) — ver el bloque SSM de abajo
# para $SSM. Los secretos van en /opt/corradi/.env, nunca en git.
rsync -a -e "$SSM" --exclude .env --exclude .git --exclude '__pycache__' ../ ubuntu@<IP>:/opt/corradi/
scp -o ProxyCommand="aws ssm start-session --target <instance-id> --document-name AWS-StartSSHSession --parameters portNumber=%p --region eu-west-1" ../.env ubuntu@<IP>:/opt/corradi/.env

# Arranca todo
eval $SSM ubuntu@<IP> 'cd /opt/corradi && docker compose up -d --build'
```

Para el flujo completo de edición/despliegue día a día (una vez la instancia ya existe), ver
la sección [Producción (AWS EC2)](../README.md#producción-aws-ec2--ya-desplegado) del README
principal.

## Coste

t4g.small: **gratis hasta 31-dic-2026** (free trial AWS, 750 h/mes) y ~17-19 €/mes después.
EBS gp3 30 GB ~2,5 €/mes. Sin NAT Gateway. La IP elástica es gratis mientras esté asociada.

## Resumen diario y semanal (cron)

Por SSM (ver acceso abajo), añade los dos crons en la instancia:
```bash
(crontab -l 2>/dev/null; \
 echo "0 20 * * * docker exec corradi-bot python -m app.scheduler.daily_summary"; \
 echo "30 20 * * 0 docker exec corradi-bot python -m app.scheduler.weekly_summary" \
) | crontab -
```
(o usa EventBridge Scheduler + una tarea, como evolución).

## Acceso a la instancia (SSM)

Con `ssh_allowed_cidr = ""` el security group **no abre el puerto 22** — la instancia no es
alcanzable por SSH directo desde ningún sitio, ni siquiera tu propia IP. El acceso real es
**SSH sobre SSM**: el agente SSM (preinstalado en la AMI de Ubuntu) tuneliza la sesión a
través de la API de AWS, autenticada con tus credenciales IAM en vez de con la red.

```bash
IID=<instance-id>          # lo imprime `terraform apply` / `terraform output`
SSM='ssh -o ProxyCommand="aws ssm start-session --target %h --document-name AWS-StartSSHSession --parameters portNumber=%p --region eu-west-1"'
eval $SSM ubuntu@$IID
```

Requiere que tu usuario IAM tenga la política de `ssm_client_user` (o permisos equivalentes
de `ssm:StartSession`), y `session-manager-plugin` instalado en tu máquina.

## Destruir

```bash
terraform destroy
```

## Seguridad / notas

- **`ssh_allowed_cidr = ""` en producción**: cierra el puerto 22 del todo; el acceso es solo
  por SSM (ver arriba). El default del `.tfvars.example` (`0.0.0.0/0`) es solo para pruebas
  rápidas de bootstrap — no lo dejes así en un despliegue real.
- La **API (8000) está cerrada** por defecto (`expose_api = false`, no tiene auth). El mapa
  público va por `expose_web = true` (80/443, Caddy con HTTPS automático, filtra las rutas
  de lectura) — la API cruda nunca queda expuesta directamente.
- El **state de Terraform** puede contener metadatos sensibles: no lo subas a git
  (`.gitignore` ya lo excluye). Para equipo, usa un backend remoto (S3 + DynamoDB lock).
- Los secretos (`GEMINI_API_KEY`, `TELEGRAM_BOT_TOKEN`) viven solo en el `.env` de la
  instancia, nunca en Terraform.
