# PFMF Backend — Droplet Deployment Guide (GitHub-based)

End-to-end handbook for taking the FastAPI backend from "code on GitHub" to
"running in production on your DigitalOcean droplet, behind Nginx, over
HTTPS with a real domain." Written for someone who has never done this
before — every command is copy-pasteable, run in order, top to bottom.

This guide assumes:

- You already have a DigitalOcean droplet created and you're SSHed into it
  as `root` (or a sudo user).
- You already have a live managed Postgres DB (DigitalOcean) and know its
  connection string — see `backend/.env` on your local machine for the
  shape of `DATABASE_URL`.
- Your code lives at `git@github.com:NabeelDevAi/PFMF.git`.
- You want future updates to be: push to GitHub → `git pull` on the
  droplet → restart the service. No CI/CD pipeline, no Docker, no
  webhooks — the simplest possible workflow, done by hand.

Replace anything in `<angle brackets>` with your real value. Run every
command block on the **droplet**, over SSH, unless a section explicitly
says "on your local machine."

---

## Table of contents

1. [Initial server setup](#1-initial-server-setup)
2. [Install system dependencies](#2-install-system-dependencies)
3. [Give the droplet access to your GitHub repo](#3-give-the-droplet-access-to-your-github-repo)
4. [Clone the repo and set up the Python environment](#4-clone-the-repo-and-set-up-the-python-environment)
5. [Configure production environment variables](#5-configure-production-environment-variables)
6. [Run database migrations](#6-run-database-migrations)
7. [Run the app manually (sanity check)](#7-run-the-app-manually-sanity-check)
8. [Run the app as a systemd service](#8-run-the-app-as-a-systemd-service)
9. [Open the firewall and confirm IP access](#9-open-the-firewall-and-confirm-ip-access)
10. [Install and configure Nginx as a reverse proxy](#10-install-and-configure-nginx-as-a-reverse-proxy)
11. [Point your domain at the droplet](#11-point-your-domain-at-the-droplet)
12. [Get a free SSL certificate with Certbot](#12-get-a-free-ssl-certificate-with-certbot)
13. [Your ongoing deploy workflow](#13-your-ongoing-deploy-workflow)
14. [Troubleshooting cheat sheet](#14-troubleshooting-cheat-sheet)

---

## 1. Initial server setup

Skip any step you've already done.

### 1.1 Create a non-root deploy user (recommended)

Running everything as `root` works, but a dedicated user is safer and is
what the rest of this guide assumes. If you'd rather stay on `root`,
skip to 1.2 — just mentally replace `deploy` with `root` everywhere below.

```bash
adduser deploy
usermod -aG sudo deploy
```

Set a password when prompted. Then copy your SSH access to the new user
so you can log in as `deploy` directly:

```bash
rsync --archive --chown=deploy:deploy ~/.ssh /home/deploy
```

From now on, log in as `ssh deploy@<droplet-ip>` and prefix commands that
need root with `sudo`.

### 1.2 Basic firewall (ufw)

```bash
sudo ufw allow OpenSSH
sudo ufw enable
sudo ufw status
```

Say `y` when asked to proceed. You should see `OpenSSH` listed as
`ALLOW`. We'll open HTTP/HTTPS ports later once Nginx is installed.

---

## 2. Install system dependencies

```bash
sudo apt update
sudo apt upgrade -y
sudo apt install -y python3.12 python3.12-venv python3-pip git nginx
```

If `python3.12` isn't available on your droplet's Ubuntu version, check
what you have with `python3 --version` — anything ≥ 3.12 is fine (the
codebase targets 3.12). On Ubuntu 24.04 it's preinstalled; on older
versions you may need the `deadsnakes` PPA:

```bash
sudo add-apt-repository -y ppa:deadsnakes/ppa
sudo apt update
sudo apt install -y python3.12 python3.12-venv
```

Verify:

```bash
python3.12 --version
git --version
nginx -v
```

---

## 3. Give the droplet access to your GitHub repo

If `PFMF` is a **private** repo, the droplet needs its own SSH key
authorized to read it. (If it's public, skip straight to §4 and use the
HTTPS clone URL instead of SSH.)

### 3.1 Generate a deploy key on the droplet

```bash
ssh-keygen -t ed25519 -C "pfmf-droplet-deploy" -f ~/.ssh/pfmf_deploy_key -N ""
cat ~/.ssh/pfmf_deploy_key.pub
```

Copy the printed public key (starts with `ssh-ed25519 ...`).

### 3.2 Add it as a Deploy Key on GitHub

On **your local machine's browser**:

1. Go to `https://github.com/NabeelDevAi/PFMF/settings/keys`
2. Click **Add deploy key**
3. Title: `PFMF droplet` (or anything memorable)
4. Paste the public key
5. Leave **"Allow write access"** unchecked — this key only needs to
   pull, never push
6. Save

### 3.3 Tell the droplet's SSH client to use this key for GitHub

```bash
cat >> ~/.ssh/config << 'EOF'
Host github.com
  HostName github.com
  User git
  IdentityFile ~/.ssh/pfmf_deploy_key
  IdentitiesOnly yes
EOF
chmod 600 ~/.ssh/config
```

Test it:

```bash
ssh -T git@github.com
```

You should see: `Hi NabeelDevAi/PFMF! You've successfully authenticated...`
(A warning about "shell access" after that is normal and expected —
deploy keys can't open a shell, only clone/pull, which is exactly what
you want.)

---

## 4. Clone the repo and set up the Python environment

```bash
sudo mkdir -p /var/www
sudo chown deploy:deploy /var/www
cd /var/www
git clone git@github.com:NabeelDevAi/PFMF.git
cd PFMF/backend
```

Create and activate a virtual environment, then install the pinned
dependencies (`requirements-lock.txt` is the exact versions the app was
tested against — use that, not `requirements.txt`, in production):

```bash
python3.12 -m venv venv
source venv/bin/activate
pip install --upgrade pip
pip install -r requirements-lock.txt
```

You should now see `(venv)` in your shell prompt. Leave it activated for
the next steps (or re-run `source venv/bin/activate` whenever you come
back to a new shell).

---

## 5. Configure production environment variables

`.env` is gitignored on purpose — it never comes from GitHub. You create
it once, by hand, on the server.

```bash
cd /var/www/PFMF/backend
nano .env
```

Paste this, filling in the real values:

```dotenv
ENVIRONMENT=production

# Your live DigitalOcean managed Postgres — same shape as your local
# backend/.env, sslmode=require is mandatory for DO managed databases.
DATABASE_URL=postgresql+psycopg://doadmin:<db-password>@<db-host>:5432/defaultdb?sslmode=require

# Generate a FRESH secret for production — do not reuse your local dev
# secret. Run: python3 -c "import secrets; print(secrets.token_hex(32))"
JWT_SECRET=<generate-a-new-one>

JWT_ACCESS_TTL_MINUTES=15
JWT_REFRESH_TTL_DAYS=30

# Your real frontend origin(s), not localhost. Add every origin the
# mobile/web app will actually call this API from.
CORS_ORIGINS=["https://your-frontend-domain.com"]

LOG_LEVEL=INFO
MAX_HORIZON_MONTHS=120
```

Save and exit (`Ctrl+O`, `Enter`, `Ctrl+X` in nano).

Lock the file down so only the deploy user can read it:

```bash
chmod 600 .env
```

Also create the local media directory (avatar uploads — this is
gitignored too, so it doesn't come from the clone):

```bash
mkdir -p media/avatars
```

---

## 6. Run database migrations

Still inside `backend/` with the venv active:

```bash
alembic upgrade head
```

Confirm it worked:

```bash
alembic current
```

You should see `0017 (head)` (or whatever the latest revision is at the
time you run this).

> If this is the **same** live DB you already migrated earlier from your
> local machine, this step will report "already at head" and do nothing —
> that's fine, it's idempotent.

---

## 7. Run the app manually (sanity check)

Before wiring up systemd, make sure the app actually boots:

```bash
uvicorn app.main:app --host 127.0.0.1 --port 8000
```

In a **second SSH session** to the same droplet:

```bash
curl http://127.0.0.1:8000/v1/health
```

You should get a JSON response back (not a connection error). Stop the
foreground process with `Ctrl+C` once confirmed — systemd will take over
running it permanently in the next step.

We bind to `127.0.0.1` (not `0.0.0.0`) deliberately: the app is never
exposed to the internet directly. Only Nginx, running locally on the
same machine, will talk to it. That's what makes SSL termination and
clean proxying possible in §10–12.

---

## 8. Run the app as a systemd service

This makes the app start on boot and auto-restart if it crashes.

```bash
sudo nano /etc/systemd/system/pfmf-backend.service
```

Paste (adjust `User=` if you're not using a `deploy` user):

```ini
[Unit]
Description=PFMF FastAPI backend
After=network.target

[Service]
Type=simple
User=deploy
WorkingDirectory=/var/www/PFMF/backend
Environment="PATH=/var/www/PFMF/backend/venv/bin"
ExecStart=/var/www/PFMF/backend/venv/bin/uvicorn app.main:app --host 127.0.0.1 --port 8000 --workers 2
Restart=always
RestartSec=3

[Install]
WantedBy=multi-user.target
```

`--workers 2` is a reasonable starting point for a small droplet (1-2
vCPUs). You can raise it later if needed.

Enable and start it:

```bash
sudo systemctl daemon-reload
sudo systemctl enable pfmf-backend
sudo systemctl start pfmf-backend
sudo systemctl status pfmf-backend
```

You should see `active (running)` in green. Confirm again:

```bash
curl http://127.0.0.1:8000/v1/health
```

---

## 9. Open the firewall and confirm IP access

Allow Nginx through the firewall (we haven't opened 80/443 yet):

```bash
sudo ufw allow 'Nginx Full'
sudo ufw status
```

We'll wire Nginx up next — once that's done, `http://<droplet-ip>/v1/health`
will work from your own browser/laptop, not just from inside the droplet.

---

## 10. Install and configure Nginx as a reverse proxy

Nginx is already installed (§2). Now point it at your app.

```bash
sudo nano /etc/nginx/sites-available/pfmf-backend
```

Paste — start with your droplet's **IP address** as `server_name`, you'll
swap in the domain in §11:

```nginx
server {
    listen 80;
    server_name <droplet-ip>;

    client_max_body_size 10M;

    location / {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
```

Enable the site and disable the default placeholder:

```bash
sudo ln -s /etc/nginx/sites-available/pfmf-backend /etc/nginx/sites-enabled/
sudo rm -f /etc/nginx/sites-enabled/default
sudo nginx -t
```

`nginx -t` should say `syntax is ok` / `test is successful`. Then reload:

```bash
sudo systemctl reload nginx
```

### Confirm public IP access

From **your local machine** (not the droplet):

```bash
curl http://<droplet-ip>/v1/health
```

Or just open `http://<droplet-ip>/v1/health` in a browser. This is your
"it's publicly reachable" checkpoint before adding a domain.

---

## 11. Point your domain at the droplet

This part happens wherever your domain is registered/managed (Namecheap,
GoDaddy, DigitalOcean DNS, Cloudflare, etc.) — not on the droplet.

1. Go to your domain's DNS management page.
2. Add an **A record**:
   - Host/Name: `@` (for the root domain) or `api` (for `api.yourdomain.com`)
   - Value/Points to: `<droplet-ip>`
   - TTL: default is fine (usually 3600 or "Automatic")
3. If you want both `yourdomain.com` and `www.yourdomain.com`, add a
   second A record for `www` pointing to the same IP (or a CNAME `www` →
   `yourdomain.com`).

DNS propagation can take a few minutes to a few hours. Check it's live:

```bash
dig +short yourdomain.com
```

Once that prints your droplet's IP, update the Nginx config to match:

```bash
sudo nano /etc/nginx/sites-available/pfmf-backend
```

Change:

```nginx
server_name <droplet-ip>;
```

to:

```nginx
server_name yourdomain.com www.yourdomain.com;
```

Then:

```bash
sudo nginx -t
sudo systemctl reload nginx
```

Confirm: `curl http://yourdomain.com/v1/health` should now work.

---

## 12. Get a free SSL certificate with Certbot

```bash
sudo apt install -y certbot python3-certbot-nginx
```

Run Certbot's Nginx plugin — it edits your Nginx config automatically to
add HTTPS and redirect HTTP → HTTPS:

```bash
sudo certbot --nginx -d yourdomain.com -d www.yourdomain.com
```

Follow the prompts:
- Enter your email (for renewal/expiry notices)
- Agree to the terms of service
- When asked about redirecting HTTP to HTTPS, choose **yes** (redirect)

Certbot will report success and show you the cert's expiry (~90 days).

Confirm HTTPS works:

```bash
curl https://yourdomain.com/v1/health
```

### Auto-renewal

Certbot installs a systemd timer automatically. Confirm it's active:

```bash
sudo systemctl status certbot.timer
```

Test that renewal would succeed (dry run, doesn't actually renew):

```bash
sudo certbot renew --dry-run
```

That's it — certs renew themselves going forward, nothing further to do.

---

## 13. Your ongoing deploy workflow

This is the loop you'll repeat every time you push new backend code.

**On your local machine:** commit and push to GitHub as normal.

**On the droplet**, pull and restart:

```bash
cd /var/www/PFMF
git pull
cd backend
source venv/bin/activate
pip install -r requirements-lock.txt   # only needed if dependencies changed
alembic upgrade head                    # only needed if new migrations exist
sudo systemctl restart pfmf-backend
sudo systemctl status pfmf-backend      # confirm it came back up clean
```

If you want this as a single command, save it as a script:

```bash
nano ~/deploy.sh
```

```bash
#!/usr/bin/env bash
set -e
cd /var/www/PFMF
git pull
cd backend
source venv/bin/activate
pip install -r requirements-lock.txt
alembic upgrade head
sudo systemctl restart pfmf-backend
echo "Deployed. Status:"
sudo systemctl status pfmf-backend --no-pager
```

```bash
chmod +x ~/deploy.sh
```

From then on, a deploy is just:

```bash
~/deploy.sh
```

---

## 14. Troubleshooting cheat sheet

**App won't start / crashes immediately:**

```bash
sudo systemctl status pfmf-backend
sudo journalctl -u pfmf-backend -n 100 --no-pager
```

Most common cause: a missing/wrong value in `.env` (the app fails fast
on startup if a required setting is missing — see
`backend/app/core/config.py`).

**Nginx 502 Bad Gateway:**

Means Nginx is up but can't reach the app. Check the app is actually
running:

```bash
sudo systemctl status pfmf-backend
curl http://127.0.0.1:8000/v1/health
```

**`nginx -t` fails:**

Read the error — it names the exact file/line. Usually a typo or a
missing semicolon in the config.

**Certbot fails to get a certificate:**

Almost always DNS — the domain isn't pointing at the droplet yet, or
propagation hasn't finished. Recheck with `dig +short yourdomain.com`
and make sure it matches your droplet's IP before retrying.

**Check what's actually listening on the droplet:**

```bash
sudo ss -tlnp
```

You should see Nginx on `:80`/`:443` and uvicorn on `127.0.0.1:8000`
only (not `0.0.0.0:8000` — if it is, double check the `--host` flag in
the systemd unit).

**View live app logs while testing:**

```bash
sudo journalctl -u pfmf-backend -f
```

`Ctrl+C` to stop following.
