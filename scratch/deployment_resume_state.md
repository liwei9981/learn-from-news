# DigitalOcean Deployment - Resume State

## What We Have Completed So Far:
1. **Dockerized the App**: We successfully created the `Dockerfile` and `docker-compose.yml` locally.
2. **GitHub Actions Workflow**: We created the `.github/workflows/deploy.yml` pipeline locally.
3. **GitHub Push**: We initialized git, cleaned up log files, created a new private repository (`liwei9981/learn-from-news`), and pushed all code to GitHub.
4. **Server Git Clone**: On the DigitalOcean droplet, we bypassed the password block using a Personal Access Token and successfully cloned the repository into `/app/learn-from-news`.
5. **.env Configuration**: We successfully pasted and saved your API keys into the `.env` file on the server.

## Current State / The Confusion:
- After exiting the `.env` file, the server automatically opened the `storage_state.json` file in the `nano` editor. 
- You pasted some text, but it was likely your `.env` text again instead of the large 13KB NotebookLM cookie file. 

## What to Do Tomorrow (Phase 1 Final Step & Phase 2):

### 1. Fix the `storage_state.json` file
When you are back on your DigitalOcean droplet, run this command to re-open the file:
```bash
nano /app/learn-from-news/.local/notebooklm-storage/storage_state.json
```
- Open `.local/notebooklm-storage/storage_state.json` on your Mac.
- Copy everything inside it.
- Paste it into the `nano` window on the server.
- Press `Ctrl + O`, `Enter`, `Ctrl + X` to save and exit.

### 2. Generate Deploy Keys (Phase 2)
Run this command on your **Mac** to generate the SSH key GitHub needs to talk to your server:
```bash
ssh-keygen -t ed25519 -C "github-actions-deploy" -f ~/.ssh/github_actions_deploy
```

### 3. Add Keys to Server and GitHub
- Copy the public key (`cat ~/.ssh/github_actions_deploy.pub`) and append it to your DigitalOcean droplet's `~/.ssh/authorized_keys` file.
- Add the private key (`cat ~/.ssh/github_actions_deploy`) to your GitHub Repository Secrets as `SSH_PRIVATE_KEY`.
- Also add `HOST` (your droplet IP) and `USERNAME` (root) to the GitHub Secrets.

### 4. Trigger the Pipeline
Make a small change to a file on your Mac, and run:
```bash
git add .
git commit -m "Trigger deployment"
git push origin main
```
Your bot will then automatically deploy and run!
