# Subir Pizza Pizza Eyes no Gerenciador Docker (Hostinger VPS)

Painel: **VPS → srv… → Gerenciador Docker → Compose → Implantar**

## 1) Publicar o código no GitHub

Repo já criado: **https://github.com/NogueiraTNT/ppf-eyes** (privado).

Para atualizar depois de mudanças locais:

```bash
cd /Applications/XAMPP/xamppfiles/htdocs/PPF/ppf-eyes
git add -A && git commit -m "update" && git push
```

> **Repo privado:** no Hostinger, autorize a conta GitHub / token.  
> Se o painel só aceitar URL pública, temporariamente: GitHub → Settings → Change visibility → Public.

## 2) URL para colar no Hostinger

```text
https://raw.githubusercontent.com/NogueiraTNT/ppf-eyes/main/docker-compose.yml
```

Ou:

```text
https://github.com/NogueiraTNT/ppf-eyes/blob/main/docker-compose.yml
```

**Nome do projeto:** `pizza-pizza-eyes`

Clique **Implantar**. A Hostinger clona o repo e faz `docker compose up --build`.

> Repo **privado**: no painel Hostinger, autorize GitHub / use token, ou torne o repo público só para o deploy.

## 3) Variáveis de ambiente (importante)

Depois de implantar (ou antes, se o painel pedir), configure no mínimo:

| Variável | Exemplo |
|---|---|
| `APP_SECRET_KEY` | string longa aleatória |
| `ADMIN_PASSWORD` | senha forte |
| `MYSQL_PASSWORD` | senha forte |
| `MYSQL_ROOT_PASSWORD` | senha forte |
| `CORS_ORIGINS` | `http://SEU_IP` |
| `ANTHROPIC_API_KEY` | sua key Claude (ou outra) |

Modelo: `.env.hostinger.example`

Se a Hostinger permitir editar `.env` na pasta do projeto:

```bash
# Web console SSH
cd /caminho/do/projeto   # onde está o docker-compose.yml
cp .env.hostinger.example .env
nano .env
docker compose up -d --build
```

## 4) Abrir o sistema

- Site: `http://SEU_IP` (porta 80)
- Health: `http://SEU_IP/api/health`
- Login: `ADMIN_USERNAME` / `ADMIN_PASSWORD` do `.env`

## 5) Atualizar depois de um push

Opções:

**A)** No Gerenciador Docker → projeto → **Rebuild / Atualizar** (se houver)

**B)** SSH (Web console):

```bash
cd /caminho/do/projeto
git pull origin main
docker compose up -d --build
```

**C)** GitHub Actions (já existe em `.github/workflows/deploy-vps.yml`) se configurar secrets SSH.

## Serviços que sobem

| Serviço | Função |
|---|---|
| `web` | Nginx + React (porta 80) |
| `api` | Python FastAPI + worker de câmeras |
| `db` | MariaDB |

## Problemas comuns

| Erro | Solução |
|---|---|
| Build falha no `frontend` | Confirme que `package-lock.json` está no Git |
| Site abre, login não | Ajuste `CORS_ORIGINS` para o IP/domínio exato |
| Câmera offline | RTSP da loja precisa alcançar a VPS (VPN/IP público) |
| Compose pede senha | Defina `MYSQL_PASSWORD` e `MYSQL_ROOT_PASSWORD` |
