# Telegram Bot Deployment Guide: Macbook -> GitHub -> DigitalOcean

This guide outlines the end-to-end process of developing a Dockerized Telegram bot locally on a Macbook, pushing it to GitHub, and setting up an automated continuous deployment (CI/CD) pipeline that syncs your code to a DigitalOcean droplet.

## Phase 1: Server Preparation (DigitalOcean)

Before automating anything, your server needs to be prepared to run the bot.

1. **Create a Droplet:** Spin up an Ubuntu droplet on DigitalOcean.
2. **Install Docker & Docker Compose V2:** SSH into your droplet and install the modern Docker engine. Ensure `docker compose` (with a space) works.
   ```bash
   sudo apt update
   sudo apt install docker.io docker-compose-v2 git
   ```
3. **Initial Clone:** 
   Clone your repository to the server manually the first time so the folder exists for the automated script to navigate into.
   ```bash
   mkdir -p /app
   cd /app
   git clone https://github.com/yourusername/your-repo.git
   ```
4. **Environment Variables:**
   Since `.env` files should **never** be tracked in Git, you must manually create or copy your `.env` file to the server.
   ```bash
   cd /app/your-repo
   nano .env # Paste your API keys and save
   ```

## Phase 2: Setting up GitHub Secrets for Authentication

For GitHub Actions to automatically update your Droplet, it needs secure SSH access. 

1. **Generate an SSH Keypair:**
   Run this on your Macbook to generate a specific deployment key:
   ```bash
   ssh-keygen -t ed25519 -C "github-actions-deploy"
   ```
2. **Add Public Key to Droplet:**
   Copy the contents of the public key (`.pub` file) and append it to the `~/.ssh/authorized_keys` file on your DigitalOcean droplet.
3. **Add Private Key to GitHub:**
   Go to your GitHub Repository -> **Settings** -> **Secrets and variables** -> **Actions** -> **New repository secret**.
   Add the following three secrets:
   - `HOST`: Your DigitalOcean Droplet's IP address.
   - `USERNAME`: The SSH user (usually `root` or `ubuntu`).
   - `SSH_PRIVATE_KEY`: The raw contents of the private key you just generated.

## Phase 3: The GitHub Actions Workflow

Create a file in your project on your Macbook at `.github/workflows/deploy.yml`:

```yaml
name: Deploy to DigitalOcean

on:
  push:
    branches: [ main ] # Triggers automatically when you push to main

jobs:
  deploy:
    runs-on: ubuntu-latest
    steps:
      - name: Checkout code
        uses: actions/checkout@v3

      - name: Deploy to Droplet via SSH
        uses: appleboy/ssh-action@master
        with:
          host: ${{ secrets.HOST }}
          username: ${{ secrets.USERNAME }}
          key: ${{ secrets.SSH_PRIVATE_KEY }}
          script: |
            # 1. Navigate to the folder you created in Phase 1
            cd /app/your-repo
            
            # 2. Pull the latest code from GitHub
            git pull origin main
            
            # 3. Rebuild and restart the Docker container
            # CRITICAL LESSON: Always use 'docker compose' (V2 syntax with a space)
            # Do NOT use 'docker-compose' (with a hyphen) as it will cause a "command not found" error in non-interactive SSH sessions!
            docker compose up -d --build
```

## Phase 4: Push and Automate!

From your Macbook:
1. Commit your new code and the `.github/workflows/deploy.yml` file.
2. Run `git push origin main`.
3. Go to the **Actions** tab on your GitHub repository. You will see the workflow running. It will SSH into your server, pull the latest code, and restart the Docker container completely seamlessly!

> **Troubleshooting Tip:** If your workflow fails but the code is updated on DigitalOcean anyway, check the GitHub Action logs! It usually means `git pull` worked, but the container build failed (e.g., due to syntax errors in your `Dockerfile` or using the outdated `docker-compose` command).
