# AMI más reciente de Ubuntu 24.04 (Noble) para ARM64
data "aws_ami" "ubuntu" {
  most_recent = true
  owners      = ["099720109477"] # Canonical

  filter {
    name   = "name"
    values = ["ubuntu/images/hvm-ssd*/ubuntu-noble-24.04-arm64-server-*"]
  }
  filter {
    name   = "virtualization-type"
    values = ["hvm"]
  }
}

resource "aws_key_pair" "this" {
  key_name   = "${var.project_name}-key"
  public_key = file(var.public_key_path)
}

resource "aws_security_group" "this" {
  name        = "${var.project_name}-sg"
  description = "CORRADI: SSH y API (opcional). El bot solo necesita salida."

  # SSH directo: OPCIONAL y desactivado por defecto. El acceso normal es por SSM
  # (ver `Host corradi` en ~/.ssh/config), que no necesita puertos de entrada y no
  # depende de la IP de origen — el ISP doméstico cambiaba de bloque varias veces al
  # día y cada vez dejaba fuera. Poner un CIDR aquí solo si se necesita SSH directo.
  dynamic "ingress" {
    for_each = var.ssh_allowed_cidr == "" ? [] : [1]
    content {
      description = "SSH"
      from_port   = 22
      to_port     = 22
      protocol    = "tcp"
      cidr_blocks = [var.ssh_allowed_cidr]
    }
  }

  dynamic "ingress" {
    for_each = var.expose_api ? [1] : []
    content {
      description = "API FastAPI"
      from_port   = 8000
      to_port     = 8000
      protocol    = "tcp"
      cidr_blocks = [var.api_allowed_cidr]
    }
  }

  # Mapa público (Caddy). El 80 es imprescindible además del 443: Let's Encrypt lo usa
  # para validar el dominio y Caddy redirige HTTP -> HTTPS.
  dynamic "ingress" {
    for_each = var.expose_web ? [80, 443] : []
    content {
      description = "Mapa publico (Caddy)"
      from_port   = ingress.value
      to_port     = ingress.value
      protocol    = "tcp"
      cidr_blocks = ["0.0.0.0/0"]
    }
  }

  egress {
    description = "Salida a internet (Telegram, Gemini, Docker Hub, apt)"
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }

  tags = { Project = var.project_name }
}

# ─── Acceso por SSM Session Manager ────────────────────────────────────────────
# Alternativa al SSH filtrado por IP: el agente de SSM (ya viene en la AMI de Ubuntu)
# abre la conexión DESDE la instancia hacia AWS, así que no hace falta ningún puerto
# de entrada abierto ni saber la IP de quien se conecta. Resuelve de raíz que el ISP
# doméstico cambie de bloque cada dos por tres.
resource "aws_iam_role" "ssm" {
  name = "${var.project_name}-ssm-role"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect    = "Allow"
      Principal = { Service = "ec2.amazonaws.com" }
      Action    = "sts:AssumeRole"
    }]
  })

  tags = { Project = var.project_name }
}

# Política gestionada por AWS: lo mínimo para que el agente hable con Systems Manager.
resource "aws_iam_role_policy_attachment" "ssm_core" {
  role       = aws_iam_role.ssm.name
  policy_arn = "arn:aws:iam::aws:policy/AmazonSSMManagedInstanceCore"
}

resource "aws_iam_instance_profile" "ssm" {
  name = "${var.project_name}-ssm-profile"
  role = aws_iam_role.ssm.name
}

# Permisos para el LADO CLIENTE (el usuario IAM que se conecta). Mínimos y acotados a
# esta instancia: abrir sesión, túnel SSH sobre SSM y ejecutar comandos puntuales.
resource "aws_iam_policy" "ssm_client" {
  count = var.ssm_client_user == "" ? 0 : 1
  name  = "${var.project_name}-ssm-client"

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        # Estas acciones no admiten acotar por recurso.
        Effect   = "Allow"
        Action   = ["ssm:DescribeInstanceInformation", "ssm:DescribeSessions",
        "ssm:GetConnectionStatus", "ssm:GetCommandInvocation", "ssm:ListCommandInvocations"]
        Resource = "*"
      },
      {
        Effect = "Allow"
        Action = ["ssm:StartSession"]
        Resource = [
          aws_instance.this.arn,
          "arn:aws:ssm:${var.region}::document/AWS-StartSSHSession",
          "arn:aws:ssm:${var.region}::document/AWS-StartPortForwardingSession",
          "arn:aws:ssm:${var.region}::document/SSM-SessionManagerRunShell",
        ]
      },
      {
        # Solo sobre las sesiones propias.
        Effect   = "Allow"
        Action   = ["ssm:TerminateSession", "ssm:ResumeSession"]
        Resource = "arn:aws:ssm:*:*:session/$${aws:username}-*"
      },
      {
        Effect   = "Allow"
        Action   = ["ssm:SendCommand"]
        Resource = [aws_instance.this.arn, "arn:aws:ssm:${var.region}::document/AWS-RunShellScript"]
      },
    ]
  })
}

resource "aws_iam_user_policy_attachment" "ssm_client" {
  count      = var.ssm_client_user == "" ? 0 : 1
  user       = var.ssm_client_user
  policy_arn = aws_iam_policy.ssm_client[0].arn
}

resource "aws_instance" "this" {
  ami                         = data.aws_ami.ubuntu.id
  instance_type               = var.instance_type
  key_name                    = aws_key_pair.this.key_name
  vpc_security_group_ids      = [aws_security_group.this.id]
  associate_public_ip_address = true
  iam_instance_profile        = aws_iam_instance_profile.ssm.name

  user_data = templatefile("${path.module}/user_data.sh.tftpl", {
    repo_url = var.repo_url
  })

  root_block_device {
    volume_type = "gp3"
    volume_size = var.root_volume_gb
    encrypted   = true
  }

  tags = {
    Name    = var.project_name
    Project = var.project_name
  }
}

resource "aws_eip" "this" {
  count    = var.use_elastic_ip ? 1 : 0
  instance = aws_instance.this.id
  domain   = "vpc"
  tags     = { Project = var.project_name }
}

locals {
  public_ip = var.use_elastic_ip ? aws_eip.this[0].public_ip : aws_instance.this.public_ip
}
