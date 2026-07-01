# Elevate IQ Website

## What's inside
- index.html — home page
- about.html, openings.html, contact.html — supporting pages
- login.html, register.html — auth pages, connected to the Python backend below
- style.css — shared glassmorphism styling for every page
- app.py — Flask backend that handles /register and /login using MySQL
- schema.sql — creates the MySQL database and users table
- requirements.txt — Python packages needed
- .env.example — copy this to .env and fill in your real MySQL credentials

## How to run it

### 1. View the website only (no database)
Just double-click index.html to open it in your browser. All pages and navigation work.
The login/register forms will show a "could not reach the server" message until you start the backend below.

### 2. Set up MySQL
Make sure MySQL is installed and running, then run:
    mysql -u root -p < schema.sql
This creates the elevateiq database and a users table.

### 3. Set up the backend
    pip install -r requirements.txt
Copy .env.example to .env and fill in your real MySQL username/password:
    DB_HOST=localhost
    DB_USER=root
    DB_PASSWORD=your_mysql_password
    DB_NAME=elevateiq

### 4. Run the backend
    python app.py
This starts the server at http://localhost:5000

### 5. Use the site
Open index.html in your browser, click "Get started" to register, then "Log in" to sign back in.
The forms call the backend automatically (API_BASE is set at the top of login.html and register.html —
update that if you deploy the backend somewhere other than localhost).
