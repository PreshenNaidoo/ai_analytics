# Windows Setup Guide (Main Branch)

This guide is for the current `main` branch.

What is runnable on this branch:
- The main working path is `agents_runtime/tests/smoke_agents_runtime.ipynb`
- There is no `scripts/dev-up.sh` flow on this branch

## 1. Install WSL + Ubuntu

### 1.1 Open PowerShell as Administrator

On Windows:
1. Press `Start`
2. Type `PowerShell`
3. Right-click `Windows PowerShell`
4. Click `Run as administrator`

### 1.2 Install WSL + Ubuntu

Run:

```powershell
wsl --install
```

What you should see:
- WSL and Ubuntu install messages
- A restart prompt

Then restart Windows.

### 1.3 Complete Ubuntu first run

After restart, open Ubuntu.
Create:
- Ubuntu username
- Ubuntu password

Keep these credentials safe.

### 1.4 How to open Ubuntu terminal later

Option A:
1. Press `Start`
2. Type `Ubuntu`
3. Open the `Ubuntu` app

Option B (from PowerShell):

```powershell
wsl
```

All `bash` commands below must run in this Ubuntu terminal.

## 2. Update Ubuntu and install tools

### 2.1 Update packages

Run:

```bash
sudo apt update && sudo apt upgrade -y
```

### 2.2 Install core tools

Run:

```bash
sudo apt install -y git curl build-essential python3 python3-pip python3-venv
```

### 2.3 Install Node.js 20

Run:

```bash
curl -fsSL https://deb.nodesource.com/setup_20.x | sudo -E bash -
sudo apt install -y nodejs
```

### 2.4 Install `uv`

Run:

```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
```

Close and reopen Ubuntu terminal.

### 2.5 Verify tool versions

Run:

```bash
python3 --version
node -v
npm -v
uv --version
```

If any command fails, fix that before continuing.

## 3. Clone the repository

### 3.1 Create a projects folder

Run:

```bash
mkdir -p ~/Projects
cd ~/Projects
```

### 3.2 Clone repo

Run:

```bash
git clone <YOUR_REPO_URL>
cd ai_analytics
```

### 3.3 Confirm location

Run:

```bash
pwd
```

Expected path format:
- `/home/<your-user>/Projects/ai_analytics`

## 4. Install project dependencies

This repo is already initialized for `uv`.
Do **not** run `uv init`.

### 4.1 Install root dependencies

From repo root, run:

```bash
uv sync
```

### 4.2 Install `agents_runtime` dependencies

Run:

```bash
cd agents_runtime
uv sync
cd ..
```

If `uv sync` fails, stop and fix it before moving on.

## 5. Install/verify MCP tools

The runtime starts these tools:
- `mssql-mcp-server`
- `@antv/mcp-server-chart` via `npx`
- `@sylphx/pdf-reader-mcp` via `npx`
- `office-word-mcp-server` via `uvx`
- `excel-mcp-server` via `uvx`

### 5.1 Install MSSQL MCP server (required)

Run:

```bash
npm install -g mssql-mcp-server
```

Verify:

```bash
mssql-mcp-server --help
```

### 5.2 Verify on-demand MCP commands

Run:

```bash
npx -y @antv/mcp-server-chart --help
npx -y @sylphx/pdf-reader-mcp --help
uvx --from office-word-mcp-server word_mcp_server --help
uvx excel-mcp-server stdio --help
```

If any command fails, fix it before continuing.

## 6. Configure SQL Server on Windows

Goal: allow Ubuntu (WSL) to connect to SQL Server running on Windows.

### 6.1 Enable TCP/IP for SQL Server

On Windows:
1. Open `SQL Server Configuration Manager`
2. Go to `SQL Server Network Configuration` -> `Protocols for <INSTANCE>`
3. Enable `TCP/IP`
4. Restart SQL Server service

### 6.2 Use SQL authentication

Create/use a SQL login with:
- Username
- Password
- Permission to read your target database

### 6.3 Open firewall port (if needed)

Allow inbound TCP on SQL Server port (usually `1433`).

If your SQL Server uses a different port, use that port in `.env`.

## 7. Find SQL host from WSL

Inside Ubuntu, test host in this order:
1. `localhost`
2. Windows host IP from:

```bash
cat /etc/resolv.conf | grep nameserver
```

Example usable host values:
- `localhost`
- `172.x.x.x` (nameserver IP)

## 8. Open the project in your IDE

Before configuring environment variables, open the project folder in your preferred IDE.

Project folder to open:
- `/home/<your-user>/Projects/ai_analytics`

Examples:
- VS Code: `File` -> `Open Folder` -> select `ai_analytics`
- Cursor: `File` -> `Open Folder` -> select `ai_analytics`
- PyCharm: `Open` -> select `ai_analytics`

After opening the project, continue with `.env` setup.

## 9. Configure `.env`

Create/edit `.env` in repo root (`ai_analytics/.env`).

Open file:

```bash
nano .env
```

Add minimum required values:

```env
OPENAI_API_KEY=sk-...
MSSQL_CONNECTION_STRING=Server=tcp:<HOST>,1433;Database=<DB_NAME>;User Id=<SQL_USER>;Password=<SQL_PASSWORD>;Encrypt=yes;TrustServerCertificate=yes;
```

### 9.1 Choose your model provider

This project now supports provider routing through LiteLLM.
Set API keys in `.env`.
Set `model_general` and `model_planner` defaults in:
- `agents_runtime/src/agents_runtime/config.py`

You can also override model names from `.env` using:
- `MODEL_GENERAL`
- `MODEL_PLANNER`

Option A: OpenAI

```env
OPENAI_API_KEY=sk-...
```

Option B: Anthropic (Claude)

```env
ANTHROPIC_API_KEY=your_anthropic_key
```

Option C: Grok (xAI)

```env
XAI_API_KEY=your_xai_key
```

If you want to set model names from `.env` instead of `config.py`, add:

```env
# OpenAI example:
# MODEL_GENERAL=gpt-4.1-mini
# MODEL_PLANNER=gpt-4.1-mini

# Anthropic example:
# MODEL_GENERAL=anthropic/claude-3-5-sonnet-latest
# MODEL_PLANNER=anthropic/claude-3-5-sonnet-latest

# Grok example:
MODEL_GENERAL=xai/grok-2-latest
MODEL_PLANNER=xai/grok-2-latest
```

### 9.2 Other optional values

```env
CHROMA_DIR=.chroma_ai_analytics
DEFAULT_AGENT_TEMPERATURE=0.5
SQL_ANALYST_TEMPERATURE=0.1
```

Save and exit (`Ctrl+O`, Enter, `Ctrl+X`).

Important:
- Keep `.env` in repo root
- Never commit `.env`

## 10. Run the smoke test notebook

### 10.1 Start Jupyter Lab

From repo root, run:

```bash
uv run --with ipykernel jupyter lab
```

### 10.2 Open notebook

Open:
- `agents_runtime/tests/smoke_agents_runtime.ipynb`

### 10.3 Run all cells top-to-bottom

Expected result:
- Runtime context loads
- Query flow runs
- Markdown output is produced

If you get DB connection errors, re-check Steps 6, 7, and 8.

## 11. Troubleshooting

### 11.1 SQL connection failure

Check:
- SQL Server is running on Windows
- TCP/IP enabled
- Firewall port open
- SQL username/password correct
- `.env` connection string host is reachable from WSL

### 11.2 MCP command not found

Re-check:
- Node/npm installed
- `uv` installed
- Step 5 commands pass

### 11.3 Private repo auth fails in WSL

Use SSH keys in WSL and clone via `git@github.com:...`.

---

Share this file with any developer onboarding this project on Windows.
