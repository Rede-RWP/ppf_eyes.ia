# Deploy Pizza Pizza Eyes na VPS (Hostinger KVM)

## O KVM 2 aguenta?

**Sim, para o uso típico.** Plano ~2 vCPU / 8 GB RAM / 100 GB:

| Carga | Na VPS? | Observação |
|---|---|---|
| Painel React + Nginx | leve | ok |
| FastAPI + MySQL | leve/médio | ok |
| Captura RTSP (OpenCV/FFmpeg) | médio | 5–15 câmeras ok se intervalo ≥20–30s |
| Visão (Claude/OpenAI/Gemini) | **não** | roda na cloud; a VPS só envia JPEG |

Reserve ~2–3 GB para SO+Docker+MariaDB; sobra folga. Se passar de ~20 câmeras agressivas, suba intervalo ou planeje KVM 4.

### Atenção crítica: câmeras locais

Se o NVR/câmeras estão na **rede local da loja** (`192.168.x.x`), a VPS em Boston **não alcança** o RTSP sozinha.

Opções:
1. **VPN** (WireGuard/Tailscale) entre loja e VPS
2. NVR com **IP/DNS público** + porta 554 liberada (menos seguro)
3. Rodar o **agente de captura na loja** e só o painel na VPS (evolução futura)

Sem uma dessas, o painel sobe, mas o teste RTSP falha.

---

## Passo a passo Hostinger

### 1) SSH na VPS

No painel Hostinger → Web console ou:

```bash
ssh root@SEU_IP
```

### 2) Instalar Docker

```bash
apt update && apt upgrade -y
curl -fsSL https://get.docker.com | sh
systemctl enable --now docker
docker --version
docker compose version
```

### 3) Firewall (UFW)

```bash
ufw allow OpenSSH
ufw allow 80/tcp
ufw allow 443/tcp
ufw enable
ufw status
```

**Não** abra MySQL (3306) para a internet.

### 4) Enviar o projeto

Do seu Mac (pasta `ppf-eyes`):

```bash
cd /Applications/XAMPP/xamppfiles/htdocs/PPF
rsync -avz --exclude node_modules --exclude .venv --exclude data \
  --exclude frontend/dist --exclude '*.db' \
  ppf-eyes/ root@SEU_IP:/opt/ppf-eyes/
```

Ou clone de um git remoto, se preferir.

### 5) Configurar `.env` na VPS

```bash
cd /opt/ppf-eyes
cp .env.production.example .env
nano .env
```

Preencha no mínimo:
- `APP_SECRET_KEY` (longa)
- `ADMIN_PASSWORD`
- `MYSQL_PASSWORD` / `MYSQL_ROOT_PASSWORD`
- `CORS_ORIGINS=http://SEU_IP` (ou `https://seu.dominio`)
- `ANTHROPIC_API_KEY` (ou outra key do provedor)

Se usar **HTTPS** depois: `AUTH_COOKIE_SECURE=true` e `CORS_ORIGINS=https://...`

### 6) Subir

```bash
cd /opt/ppf-eyes
docker compose up -d --build
docker compose ps
docker compose logs -f --tail=80 api
```

Abra: `http://SEU_IP`  
Login: usuário/senha do `.env`

Health: `http://SEU_IP/api/health`

### 7) (Opcional) HTTPS com domínio

1. Aponte o DNS A do domínio para o IP da VPS.
2. Instale Caddy ou Certbot na frente da porta 80, **ou** adicione um serviço `caddy` no compose.

Exemplo rápido com Certbot + nginx no host (se preferir):

```bash
apt install -y certbot python3-certbot-nginx
# depois de apontar DNS e adaptar proxy — ou use Caddy
```

Com HTTPS ligado, atualize `.env` (`CORS_ORIGINS`, `AUTH_COOKIE_SECURE=true`) e:

```bash
docker compose up -d --force-recreate api web
```

### 8) Atualizar depois de mudanças

Prefira o fluxo Git abaixo. Manual:

```bash
cd /opt/ppf-eyes
./scripts/deploy.sh
```

Snapshots ficam no volume `ppf_eyes_data`; banco no `ppf_eyes_mysql`.

---

## Deploy automático ligado ao Git (recomendado)

Fluxo: **merge/push em `main` → GitHub Actions → SSH na VPS → `git pull` + `docker compose up --build`**.

O `.env` **não** vai no Git (fica só na VPS).

### A) Criar o repositório (no seu Mac)

```bash
cd /Applications/XAMPP/xamppfiles/htdocs/PPF/ppf-eyes
git init
git add .
git commit -m "Initial PPF Eyes"
# Crie o repo no GitHub (privado) e:
git branch -M main
git remote add origin git@github.com:SEU_USER/ppf-eyes.git
git push -u origin main
```

### B) Bootstrap na VPS (uma vez)

```bash
ssh root@SEU_IP
apt update && apt install -y git
curl -fsSL https://get.docker.com | sh

# Clone (HTTPS se público; SSH se privado — ver deploy key abaixo)
git clone https://github.com/SEU_USER/ppf-eyes.git /opt/ppf-eyes
cd /opt/ppf-eyes
cp .env.production.example .env
nano .env   # senhas, CORS_ORIGINS=http://SEU_IP, API keys
chmod +x scripts/deploy.sh scripts/vps-bootstrap.sh
./scripts/deploy.sh
```

Se o repo for **privado**, na VPS use deploy key (read-only) **antes** do clone:

```bash
ssh-keygen -t ed25519 -f /root/.ssh/ppf_eyes_deploy -N ""
cat /root/.ssh/ppf_eyes_deploy.pub
# Cole no GitHub → Settings → Deploy keys → Allow read
cat >> /root/.ssh/config <<'EOF'
Host github.com
  IdentityFile /root/.ssh/ppf_eyes_deploy
  StrictHostKeyChecking accept-new
EOF
git clone git@github.com:SEU_USER/ppf-eyes.git /opt/ppf-eyes
```

### C) Chave SSH para o GitHub Actions deployar

Na VPS:

```bash
ssh-keygen -t ed25519 -f /root/.ssh/gha_deploy -N ""
cat /root/.ssh/gha_deploy.pub >> /root/.ssh/authorized_keys
cat /root/.ssh/gha_deploy   # chave PRIVADA → secret VPS_SSH_KEY
```

No GitHub → **Settings → Secrets and variables → Actions** → New repository secret:

| Secret | Valor |
|---|---|
| `VPS_HOST` | IP da VPS |
| `VPS_USER` | `root` |
| `VPS_SSH_KEY` | conteúdo de `/root/.ssh/gha_deploy` (privada) |
| `VPS_PORT` | `22` (opcional) |

Arquivo do workflow: `.github/workflows/deploy-vps.yml` (já no projeto).

### D) Testar

1. Faça um commit/push (ou merge PR) em `main`
2. Aba **Actions** no GitHub → workflow **Deploy VPS** deve ficar verde
3. `http://SEU_IP` atualiza em 1–3 min

Deploy manual sem push: Actions → Deploy VPS → **Run workflow**.

---

## Comandos úteis

```bash
docker compose logs -f api
docker compose restart api
docker compose down          # para (não apaga volumes)
docker compose down -v       # APAGA banco e dados — cuidado
```

## Checklist pós-deploy

- [ ] Login funciona
- [ ] Configurações → salvar API key + Testar IA
- [ ] Ambientes ok
- [ ] Câmera: RTSP alcançável **da VPS** (VPN/público)
- [ ] Trocar senha admin padrão
