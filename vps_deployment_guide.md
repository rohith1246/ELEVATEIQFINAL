# VPS Deployment Guide: ElevateIQ

This guide provides step-by-step instructions to deploy **ElevateIQ** (Flask + PostgreSQL + HTML/JS/CSS frontend) on an **Ubuntu VPS** using **Nginx** (as a reverse proxy and static server) and **Gunicorn** (as the Python WSGI application server).

---

## Prerequisites
- An **Ubuntu VPS** (Ubuntu 22.04 LTS or 24.04 LTS recommended)
- A **domain name** pointing to your VPS IP (e.g., `elevateiq.yourcompany.com`) or the public VPS IP address
- SSH access with root or sudo permissions

---

## Step 1: Install System Dependencies
Update your server's package list and install Python, PostgreSQL, Nginx, and Git:

```bash
sudo apt update && sudo apt upgrade -y
sudo apt install python3-pip python3-venv postgresql postgresql-contrib nginx git -y
```

---

## Step 2: Configure the PostgreSQL Database
1. Switch to the default postgres database user:
   ```bash
   sudo -i -u postgres
   ```
2. Enter the PostgreSQL interactive shell:
   ```bash
   psql
   ```
3. Create the database, database user, and grant privileges (replace `your_secure_password` with a strong password):
   ```sql
   CREATE DATABASE elevateiq_db;
   CREATE USER elevateiq_user WITH PASSWORD 'your_secure_password';
   GRANT ALL PRIVILEGES ON DATABASE elevateiq_db TO elevateiq_user;
   \q
   ```
4. Exit back to your standard shell:
   ```bash
   exit
   ```

---

## Step 3: Clone & Setup the Project
1. Navigate to the `/var/www` directory (standard location for hosting web applications):
   ```bash
   cd /var/www
   sudo git clone https://github.com/rohith1246/ELEVATEIQFINAL.git elevateiq
   sudo chown -R $USER:$USER /var/www/elevateiq
   cd elevateiq
   ```

2. Create a virtual environment and install the required dependencies:
   ```bash
   python3 -m venv venv
   source venv/bin/activate
   pip install --upgrade pip
   pip install -r requirements.txt
   pip install gunicorn
   ```

---

## Step 4: Configure Environment Variables
Create an `.env` file in the root of the project `/var/www/elevateiq/.env` containing your database connection string and secret credentials:

```ini
DATABASE_URL=postgresql://elevateiq_user:your_secure_password@localhost:5432/elevateiq_db
SECRET_KEY=generate_a_long_random_hash_here
PORT=5000
```

Initialize your database schema:
```bash
# Activate virtual environment if not already activated
source venv/bin/activate
# Run schema migration script using python
psql -U elevateiq_user -d elevateiq_db -h localhost -f schema.sql
```

---

## Step 5: Configure Gunicorn Background Service
To ensure your Flask backend runs in the background and starts automatically when the VPS restarts, create a systemd service.

1. Create a service file:
   ```bash
   sudo nano /etc/systemd/system/elevateiq.service
   ```

2. Paste the following configuration:
   ```ini
   [Unit]
   Description=Gunicorn instance to serve ElevateIQ API
   After=network.target

   [Service]
   User=ubuntu
   Group=www-data
   WorkingDirectory=/var/www/elevateiq
   Environment="PATH=/var/www/elevateiq/venv/bin"
   Environment="PYTHONPATH=/var/www/elevateiq/backend"
   EnvironmentFile=/var/www/elevateiq/.env
   ExecStart=/var/www/elevateiq/venv/bin/gunicorn --workers 3 --bind 127.0.0.1:5000 run:app

   [Install]
   WantedBy=multi-user.target
   ```
   *(Note: Adjust the `User=ubuntu` field to match your VPS username if it is not `ubuntu`).*

3. Start and enable the service:
   ```bash
   sudo systemctl start elevateiq
   sudo systemctl enable elevateiq
   ```

To verify the service is running:
```bash
sudo systemctl status elevateiq
```

---

## Step 6: Configure Nginx as a Reverse Proxy
Nginx will handle static files (`.html`, `.css`, `.png`, etc.) directly for maximum performance, and forward any API requests (`/login`, `/register`, `/chat/*`) to the backend Gunicorn service.

1. Create a new server block configuration file:
   ```bash
   sudo nano /etc/nginx/sites-available/elevateiq
   ```

2. Paste the following configuration (replace `your_domain_or_ip` with your actual domain name or VPS public IP):
   ```nginx
   server {
       listen 80;
       server_name your_domain_or_ip;

       # Frontend Static Files
       location / {
           root /var/www/elevateiq/frontend;
           index index.html;
           try_files $uri $uri/ =404;
       }

       # EduTech Portal Static Files
       location /edutech/ {
           alias /var/www/elevateiq/edutech/;
           index index.html;
           try_files $uri $uri/ =404;
       }

       # Backend API requests proxying
       location /register { proxy_pass http://127.0.0.1:5000; }
       location /login { proxy_pass http://127.0.0.1:5000; }
       location /forgot-password { proxy_pass http://127.0.0.1:5000; }
       location /reset-password { proxy_pass http://127.0.0.1:5000; }
       location /announcements { proxy_pass http://127.0.0.1:5000; }
       location /employees { proxy_pass http://127.0.0.1:5000; }
       location /profile { proxy_pass http://127.0.0.1:5000; }
       location /attendance { proxy_pass http://127.0.0.1:5000; }
       location /leaves { proxy_pass http://127.0.0.1:5000; }
       location /jobs { proxy_pass http://127.0.0.1:5000; }
       location /applications { proxy_pass http://127.0.0.1:5000; }
       location /dashboard { proxy_pass http://127.0.0.1:5000; }
       location /reports { proxy_pass http://127.0.0.1:5000; }
       location /chat { proxy_pass http://127.0.0.1:5000; }
       location /uploads { proxy_pass http://127.0.0.1:5000; }

       # General reverse proxy settings
       proxy_set_header Host $host;
       proxy_set_header X-Real-IP $remote_addr;
       proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
       proxy_set_header X-Forwarded-Proto $scheme;
   }
   ```

3. Enable the configuration and restart Nginx:
   ```bash
   sudo ln -s /etc/nginx/sites-available/elevateiq /etc/nginx/sites-enabled/
   # Remove default Nginx site config to avoid conflicts
   sudo rm /etc/nginx/sites-enabled/default
   # Test configurations
   sudo nginx -t
   # Restart server
   sudo systemctl restart nginx
   ```

---

## Step 7: Secure the Site with SSL (Let's Encrypt)
To secure logins and chat with HTTPS:

1. Install Certbot for Nginx:
   ```bash
   sudo apt install certbot python3-certbot-nginx -y
   ```
2. Run Certbot to acquire and configure the SSL certificate (replace `your_domain` with your domain):
   ```bash
   sudo certbot --nginx -d your_domain
   ```
3. Follow the interactive prompts. Certbot will automatically edit your Nginx configuration to enable SSL and redirect HTTP traffic to HTTPS.

---

## Step 8: Update Frontend API Base URL
In the frontend files (e.g. `login.html`, `dashboard.html`), make sure the `API_BASE` is configured as a relative path or your production domain:

```javascript
// In login.html, dashboard.html, etc.
const API_BASE = window.location.origin; // Dynamically uses your VPS domain/IP
```
This is already set correctly in your repository, so it will automatically work in production!
