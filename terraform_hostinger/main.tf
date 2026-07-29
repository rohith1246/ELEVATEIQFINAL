# ============================================================
# Terraform Deployment Configuration for Hostinger VPS
# Project: ElevateIQ & EduTech Enterprise Platform
# ============================================================

terraform {
  required_version = ">= 1.5.0"
  required_providers {
    null = {
      source  = "hashicorp/null"
      version = "~> 3.2"
    }
  }
}

resource "null_resource" "hostinger_vps_deploy" {
  # Forces deployment execution on apply
  triggers = {
    always_run = "${timestamp()}"
  }

  # SSH Connection Configuration using Hostinger VPS Password
  connection {
    type     = "ssh"
    host     = var.hostinger_ip
    user     = var.hostinger_user
    password = var.hostinger_password
    timeout  = "5m"
  }

  # Automated Execution Pipeline on Hostinger VPS
  provisioner "remote-exec" {
    inline = [
      "echo '=== [1/8] Updating System Packages & Installing Core Tools & PostgreSQL ==='",
      "sudo apt-get update -y",
      "sudo apt-get install -y python3 python3-venv python3-pip git nginx ufw certbot python3-certbot-nginx libpq-dev gcc openssl postgresql postgresql-contrib",
      "sudo ufw allow 80/tcp || true",
      "sudo ufw allow 443/tcp || true",
      "sudo ufw allow 22/tcp || true",

      "echo '=== [2/8] Setting Up Hostinger VPS Local PostgreSQL Database ==='",
      "sudo systemctl start postgresql",
      "sudo systemctl enable postgresql",
      "sudo -u postgres psql -c \"CREATE USER elevateiq WITH PASSWORD 'Password123!';\" || true",
      "sudo -u postgres psql -c \"CREATE DATABASE elevateiq OWNER elevateiq;\" || true",
      "sudo -u postgres psql -c \"GRANT ALL PRIVILEGES ON DATABASE elevateiq TO elevateiq;\" || true",
      "sudo -u postgres psql -c \"ALTER USER elevateiq WITH SUPERUSER;\" || true",

      "echo '=== [3/8] Setting Up Project Work Directories ==='",
      "sudo mkdir -p /var/www/elevateiq /var/www/assessments /var/www/assessments/instance",
      "sudo chown -R $USER:$USER /var/www/elevateiq /var/www/assessments",

      "echo '=== [4/8] Fetching Latest ElevateIQ & Assessments Repositories ==='",
      "if [ ! -d '/var/www/elevateiq/.git' ]; then GIT_TERMINAL_PROMPT=0 git clone https://github.com/rohith1246/ELEVATEIQFINAL.git /var/www/elevateiq; else cd /var/www/elevateiq && git fetch origin && git reset --hard origin/main; fi",
      "sudo rm -rf /tmp/assessments_clone /var/www/assessments && sudo mkdir -p /var/www/assessments /var/www/assessments/instance && sudo chown -R $USER:$USER /var/www/assessments",
      "GIT_TERMINAL_PROMPT=0 git clone https://github.com/shivapendala/assessments.git /tmp/assessments_clone",
      "if [ -f '/tmp/assessments_clone/requirements.txt' ]; then cp -a /tmp/assessments_clone/. /var/www/assessments/; elif [ -f '/tmp/assessments_clone/assessments/requirements.txt' ]; then cp -a /tmp/assessments_clone/assessments/. /var/www/assessments/; fi",
      "rm -rf /tmp/assessments_clone",

      "echo '=== [5/8] Building Python Virtual Environments & Provisioning Local VPS DB ==='",
      "cd /var/www/elevateiq && python3 -m venv venv && /var/www/elevateiq/venv/bin/pip install --upgrade pip && /var/www/elevateiq/venv/bin/pip install -r requirements.txt",
      "cd /var/www/assessments && python3 -m venv venv && /var/www/assessments/venv/bin/pip install --upgrade pip gunicorn psycopg2-binary && /var/www/assessments/venv/bin/pip install -r requirements.txt",
      
      "sudo bash -c 'cat <<EOT > /var/www/elevateiq/.env\nDATABASE_URL=postgresql://elevateiq:Password123!@127.0.0.1:5432/elevateiq\nPORT=5000\nFLASK_ENV=production\nEOT'",
      "sudo cp /var/www/elevateiq/.env /var/www/assessments/.env",

      "cd /var/www/elevateiq && /var/www/elevateiq/venv/bin/python migrate_db.py || true",
      "cd /var/www/elevateiq && /var/www/elevateiq/venv/bin/python -c 'import bcrypt, psycopg2; conn=psycopg2.connect(\"postgresql://elevateiq:Password123!@127.0.0.1:5432/elevateiq\"); cur=conn.cursor(); pw=bcrypt.hashpw(b\"Password123!\", bcrypt.gensalt()).decode(\"utf-8\"); cur.execute(\"UPDATE users SET password=%s, portal=\\\"elevateiq\\\" WHERE role IN (\\\"employee\\\", \\\"team_leader\\\", \\\"admin\\\", \\\"hr\\\", \\\"hr_manager\\\") OR email LIKE \\\"%%@gmail.com\\\";\", (pw,)); cur.execute(\"TRUNCATE TABLE account_lockouts, login_attempts;\"); conn.commit(); conn.close()' || true",

      "sudo bash -c 'cat <<EOT > /etc/systemd/system/elevateiq.service\n[Unit]\nDescription=ElevateIQ High-Concurrency WSGI Application Service\nAfter=network.target\nStartLimitIntervalSec=0\n\n[Service]\nUser=root\nWorkingDirectory=/var/www/elevateiq\nEnvironment=\"PATH=/var/www/elevateiq/venv/bin\"\nEnvironmentFile=-/var/www/elevateiq/.env\nExecStart=/var/www/elevateiq/venv/bin/gunicorn -c gunicorn.conf.py --bind 127.0.0.1:5000 backend.run:app\nRestart=always\nRestartSec=3s\n\n[Install]\nWantedBy=multi-user.target\nEOT'",

      "sudo bash -c 'cat <<EOT > /etc/systemd/system/elevateiq-assessment.service\n[Unit]\nDescription=ElevateIQ Assessment Subdomain WSGI Service\nAfter=network.target\nStartLimitIntervalSec=0\n\n[Service]\nUser=root\nWorkingDirectory=/var/www/assessments\nEnvironment=\"PATH=/var/www/assessments/venv/bin\"\nEnvironmentFile=-/var/www/assessments/.env\nExecStart=/var/www/assessments/venv/bin/gunicorn -c gunicorn.conf.py --bind 127.0.0.1:5001 \"app:create_app()\"\nRestart=always\nRestartSec=3s\n\n[Install]\nWantedBy=multi-user.target\nEOT'",

      "echo '=== [6/8] Bootstrapping SSL & Configuring Nginx Reverse Proxy ==='",
      "sudo mkdir -p /etc/letsencrypt/live/elevateiq-softtech.com /etc/letsencrypt/live/assessment.elevateiq-softtech.com",
      "if [ ! -f '/etc/letsencrypt/live/elevateiq-softtech.com/fullchain.pem' ]; then sudo openssl req -x509 -nodes -days 365 -newkey rsa:2048 -keyout /etc/letsencrypt/live/elevateiq-softtech.com/privkey.pem -out /etc/letsencrypt/live/elevateiq-softtech.com/fullchain.pem -subj '/CN=elevateiq-softtech.com'; fi",
      "if [ ! -f '/etc/letsencrypt/live/assessment.elevateiq-softtech.com/fullchain.pem' ]; then sudo openssl req -x509 -nodes -days 365 -newkey rsa:2048 -keyout /etc/letsencrypt/live/assessment.elevateiq-softtech.com/privkey.pem -out /etc/letsencrypt/live/assessment.elevateiq-softtech.com/fullchain.pem -subj '/CN=assessment.elevateiq-softtech.com'; fi",
      "if [ ! -f '/etc/letsencrypt/options-ssl-nginx.conf' ]; then sudo bash -c 'echo \"ssl_session_cache shared:le_nginx_shared:10m; ssl_session_timeout 1440m; ssl_session_tickets off; ssl_protocols TLSv1.2 TLSv1.3; ssl_ciphers ECDHE-ECDSA-AES128-GCM-SHA256:ECDHE-RSA-AES128-GCM-SHA256:ECDHE-ECDSA-AES256-GCM-SHA384:ECDHE-RSA-AES256-GCM-SHA384; ssl_prefer_server_ciphers off;\" > /etc/letsencrypt/options-ssl-nginx.conf'; fi",
      "if [ ! -f '/etc/letsencrypt/ssl-dhparams.pem' ]; then sudo openssl dhparam -out /etc/letsencrypt/ssl-dhparams.pem 2048; fi",
      "sudo cp /var/www/elevateiq/nginx.conf /etc/nginx/sites-available/elevateiq || true",
      "sudo rm -rf /etc/nginx/sites-enabled/*",
      "sudo ln -sf /etc/nginx/sites-available/elevateiq /etc/nginx/sites-enabled/default",
      "sudo nginx -t",

      "echo '=== [7/8] Issuing/Updating SSL Certificates for elevateiq-softtech.com & assessment.elevateiq-softtech.com ==='",
      "sudo certbot --nginx -d assessment.elevateiq-softtech.com --non-interactive --agree-tos -m admin@elevateiq-softtech.com --redirect --keep-until-expiring || true",
      "sudo certbot --nginx -d elevateiq-softtech.com -d www.elevateiq-softtech.com --non-interactive --agree-tos -m admin@elevateiq-softtech.com --redirect --keep-until-expiring || true",

      "echo '=== [8/8] Starting & Verifying Services ==='",
      "sudo systemctl daemon-reload",
      "sudo systemctl restart elevateiq elevateiq-assessment",
      "sudo systemctl restart nginx",
      "echo '=== [DIAGNOSTICS] Service Status ==='",
      "sudo systemctl status elevateiq --no-pager || true",
      "sudo systemctl status elevateiq-assessment --no-pager || true",
      "echo '=== [DIAGNOSTICS] Gunicorn Main Service Logs ==='",
      "sudo journalctl -u elevateiq -n 50 --no-pager || true",
      "echo '=== [DIAGNOSTICS] Gunicorn Assessment Service Logs ==='",
      "sudo journalctl -u elevateiq-assessment -n 50 --no-pager || true"
    ]
  }
}
