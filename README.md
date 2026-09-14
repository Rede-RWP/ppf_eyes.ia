# Pizza Pizza Eyes

Monitoramento de câmeras RTSP com IA de visão (OpenAI / Gemini / Claude). Detecta fora-do-padrão (sem touca, fardamento, EPI, celular excessivo, tempo de espera) e gera alertas com snapshot (com demarcação da pessoa). Inclui chat de relatórios com a IA.

## Pré-requisitos

- Python 3.9+
- Node.js 18+
- MySQL / MariaDB (XAMPP ok)
- FFmpeg (`brew install ffmpeg`)

## Setup rápido

```bash
# 1) Variáveis
cd /Applications/XAMPP/xamppfiles/htdocs/PPF/ppf-eyes
cp .env.example .env
# edite APP_SECRET_KEY, ADMIN_PASSWORD, MYSQL_* e (opcional) chaves de IA

# 2) Banco MySQL (exemplo XAMPP)
/Applications/XAMPP/xamppfiles/bin/mysql -u root <<'SQL'
CREATE DATABASE IF NOT EXISTS ppf_eyes CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
CREATE USER IF NOT EXISTS 'ppf_eyes'@'localhost' IDENTIFIED BY 'SUA_SENHA';
GRANT ALL PRIVILEGES ON ppf_eyes.* TO 'ppf_eyes'@'localhost';
FLUSH PRIVILEGES;
SQL

# 3) Backend
cd backend
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload --host 0.0.0.0 --port 8090

# 4) Frontend (outro terminal)
cd ../frontend
npm install
npm run dev
```

Abra: http://localhost:5173  
Login: usuário/senha do `.env` (`ADMIN_USERNAME` / `ADMIN_PASSWORD`)

API docs: http://localhost:8090/docs

## Segurança (login)

- Sessão JWT com `jti` revogável no MySQL (`auth_sessions`)
- Cookie **HttpOnly** (`ppf_eyes_session`) + suporte a Bearer
- Rate limit e bloqueio temporário após várias falhas
- Logout invalida a sessão no servidor
- Snapshots/favoritos só com autenticação
- Headers de segurança (nosniff, frame deny, no-store em `/api`)
- Chaves de IA criptografadas no banco
- Imagens de alerta expiram em **24h** (`SNAPSHOT_RETENTION_HOURS`); **favoritos** não são apagados; ao desfavoritar, passam a valer 24h

## Fluxo operacional

1. **Configurações** → provedor + API key.
2. **Ambientes** → regras por local (touca, farda, celular, espera).
3. **Câmeras** → RTSP + perfil.
4. **Alertas** / **Relatórios**.

### Dicas RTSP (NVR comum)

```text
rtsp://admin:SENHA@IP:554/h264/ch1/main/av_stream
```

Senha com `#` é convertida para `%23` automaticamente.

## Estrutura

- `backend/` — FastAPI + worker RTSP + MySQL
- `frontend/` — painel React
- `data/` — snapshots JPEG (metadados no MySQL)

## Docker (produção / VPS)

Stack: **MariaDB + API + Nginx (frontend)**.

```bash
cp .env.production.example .env
# edite senhas, CORS_ORIGINS=http://SEU_IP, API keys
docker compose up -d --build
```

Guia Hostinger (KVM 2):
- **Gerenciador Docker (painel):** [`HOSTINGER.md`](./HOSTINGER.md)
- SSH / Git Actions: [`DEPLOY-VPS.md`](./DEPLOY-VPS.md)

Abre na porta **80** (`http://SEU_IP`). Volumes Docker guardam MySQL e snapshots.
