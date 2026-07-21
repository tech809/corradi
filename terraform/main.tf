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

  ingress {
    description = "SSH"
    from_port   = 22
    to_port     = 22
    protocol    = "tcp"
    cidr_blocks = [var.ssh_allowed_cidr]
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

  egress {
    description = "Salida a internet (Telegram, Gemini, Docker Hub, apt)"
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }

  tags = { Project = var.project_name }
}

resource "aws_instance" "this" {
  ami                         = data.aws_ami.ubuntu.id
  instance_type               = var.instance_type
  key_name                    = aws_key_pair.this.key_name
  vpc_security_group_ids      = [aws_security_group.this.id]
  associate_public_ip_address = true

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
