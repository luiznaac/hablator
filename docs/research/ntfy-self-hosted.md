# ntfy self-hosted — findings

Research for issue [#2 (ntfy self-hosted: como integrar)](https://github.com/luiznaac/hablator/issues/2).
Fontes primárias: docs oficiais em `https://docs.ntfy.sh/` (versão referenciada na doc: ntfy v2.28.0).
Acesso em 2026-09-14. Todas as afirmações abaixo vêm dessas páginas; os links apontam para a seção exata.

Fontes:

- https://docs.ntfy.sh/publish/ — publish API, headers, JSON, auth, cache, limites
- https://docs.ntfy.sh/subscribe/api/ — subscribe via API, replay/cache
- https://docs.ntfy.sh/subscribe/phone/ — app Android/iOS, instant delivery
- https://docs.ntfy.sh/install/ — instalação, Docker
- https://docs.ntfy.sh/config/ — server.yml, auth/ACL, cache, rate limiting, iOS
- https://github.com/binwiederhier/ntfy/blob/main/server/server.yml — template de config referenciado pela doc

## 1. API de publish

Fonte: https://docs.ntfy.sh/publish/ (seções “Publishing”, “Publish as JSON”, “Authentication”,
“Advanced features → Message caching”, “Limitations”, “List of all parameters”).

### Endpoints

- `POST /<topic>` ou `PUT /<topic>` com o corpo sendo a mensagem em texto plano (`text/plain`).
  Tópicos são criados on-the-fly ao publicar/assinar.
- **Publicar como JSON**: `POST`/`PUT` na **raiz** do servidor (`https://<host>/`), com corpo
  `application/json`; o campo `topic` é o único obrigatório. Atenção: a URL é a raiz, não
  `/<topic>`.
- Webhook via GET: `/publish` (aliases `/send`, `/trigger`), com parâmetros de query
  (`?message=...&priority=high&tags=warning,skull`). `/mywebhook/trigger` publica `triggered`.

### Headers relevantes (case-insensitive; aliases entre parênteses)

| Header | Aliases | Função |
|---|---|---|
| `X-Message` | `Message`, `m` | corpo alternativo (via header) |
| `X-Title` | `Title`, `ti`, `t` | título (limite 1 KB) |
| `X-Priority` | `Priority`, `prio`, `p` | 1..5: 1=min, 2=low, 3=default, 4=high, 5=max/urgent |
| `X-Tags` | `Tags`, `tag`, `ta` | lista separada por vírgula; shortcodes de emoji; limite combinado 512 B |
| `X-Click` | `Click` | URL aberta ao tocar a notificação (http(s), `mailto:`, `geo:`, `ntfy://`, …) |
| `X-Attach` | `Attach`, `a` | URL de anexo externo |
| `X-Filename` | `Filename`, `File`, `f` | nome do arquivo (upload via PUT no corpo ou para anexo externo) |
| `X-Markdown` | `Markdown`, `md` | `true`/`1`/`yes`, ou `Content-Type: text/markdown` |
| `X-Delay` | `Delay`, `X-At`, `At`, `X-In`, `In` | entrega agendada (`30min`, `9am`, …); limite default 3d |
| `X-Cache` | `Cache` | `no` = não armazenar no cache do servidor |
| `X-Firebase` | `Firebase` | `no` = não encaminhar ao FCM |
| `X-Icon` | `Icon` | URL de ícone (JPEG/PNG) |
| `X-Sequence-ID` | `Sequence-ID`, `SID` | atualizar/limpar/deletar notificação |
| `X-Actions` | `Actions`, `Action` | até 3 botões (`view`, `broadcast`, `http`, `copy`) |

Exemplo (curl):

```bash
curl \
  -H "Title: Alerta" \
  -H "Priority: urgent" \
  -H "Tags: warning,skull" \
  -H "Click: https://app.hablator.example/session/123" \
  -d "Mensagem do hablator" \
  https://ntfy.example.com/hablator_alerts
```

### Corpo JSON (publish na raiz)

Fonte: https://docs.ntfy.sh/publish/#publish-as-json.

```json
{
  "topic": "hablator_alerts",
  "message": "Sessão encerrada com 12 acertos",
  "title": "Hablator",
  "tags": ["warning", "cd"],
  "priority": 4,
  "click": "https://app.hablator.example/session/123",
  "attach": "https://filesrv.lan/space.jpg",
  "filename": "diskspace.jpg",
  "markdown": true,
  "icon": "https://example.com/icon.png",
  "delay": "30min",
  "actions": [{"action": "view", "label": "Abrir", "url": "https://app.hablator.example"}]
}
```

Campos: `topic` (obrigatório), `message` (default `triggered` se vazio), `title`, `tags` (array),
`priority` (int 1–5), `click`, `attach`, `filename`, `markdown` (bool), `icon`, `delay`,
`actions`, `email`, `call`, `sequence_id`.

Notas:

- Mensagem > 4.096 bytes ou não-UTF-8 vira **attachment** automaticamente (a menos que
  `X-Filename` seja passado para forçar anexo mesmo em mensagens menores).
- `Cache: no` evita persistência no servidor (entrega só para subscribers conectados; `since=`
  e `poll=1` não retornam a mensagem).

## 2. Autenticação num self-hosted

Fonte: https://docs.ntfy.sh/config/#access-control e https://docs.ntfy.sh/publish/#authentication.

Por padrão o servidor é **aberto** (`auth-default-access: read-write`, todo mundo lê/escreve em
qualquer tópico). Para instância privada:

- `auth-file: /var/lib/ntfy/user.db` (SQLite criado automaticamente; habilita auth/ACL).
  Alternativa: `database-url` (Postgres) habilita auth implicitamente.
- `auth-default-access: "deny-all"` — recomendado para instância privada.

### Usuários e roles

- Roles: `user` (sem permissão especial) e `admin` (read-write em todos os tópicos).
- CLI: `ntfy user add --role=admin phil`, `ntfy user change-pass`, `ntfy user change-role`.
- Declarativo no `server.yml` / env: `auth-users` no formato
  `<username>:<bcrypt-hash>:<role>`; hash gerado com `ntfy user hash` (ou bcrypt externo).
  Ex.: `NTFY_AUTH_USERS='phil:$2a$10$...:admin'` (em Docker, escapar `$` como `$$`).

### ACL por tópico

- Permissões: `read-write` (`rw`), `read-only` (`ro`), `write-only` (`wo`), `deny`/`none`.
- Tópico pode ser nome exato ou padrão com wildcard `*` (`alerts_*`, `up*`); só `*` é suportado.
- Usuário especial `*` / `everyone` representa acesso anônimo.
- CLI: `ntfy access phil mytopic rw`, `ntfy access everyone "up*" write`.
- Declarativo: `auth-access` no formato `<username>:<topic-pattern>:<access>`, ex.:
  `auth-access: ["backup-script:backups:rw", "*:announcements:ro"]`.

### Access tokens

- CLI: `ntfy token add [--expires=30d] [--label="..."] <user>`; token no formato `tk_` + 32 chars.
- Declarativo: `auth-tokens` no formato `<username>:<token>[:<label>]`; tokens precisam começar
  com `tk_` e ter 32 chars. Máximo de 60 tokens por usuário.
- **Hoje o token dá acesso total à conta do usuário** (sem escopo granular; roadmap).
- Uso no publish: `Authorization: Bearer tk_...`, ou Basic com usuário vazio
  (`curl -u :tk_...`), ou `?auth=<base64 raw do header Authorization>`.

### Recomendação para instância single-user (hablator)

1. `auth-default-access: deny-all` + `auth-file` persistido.
2. Um usuário `admin` (dono do telefone) via `auth-users`/CLI.
3. Um access token dedicado para o backend do hablator publicar (`auth-tokens` ou
   `ntfy token add --label=hablator`); guardar em variável de ambiente/secret do serviço.
4. Não é necessária ACL por tópico para o admin; o token herda o acesso total do usuário admin.
5. **HTTPS obrigatório** — Basic auth só codifica, não criptografa (avisado na doc).

## 3. Tópicos e app do celular

Fonte: https://docs.ntfy.sh/publish/#picking-a-topic e https://docs.ntfy.sh/subscribe/phone/.

- Nomes de tópico: apenas `[-_A-Za-z0-9]`, até 64 caracteres; criados on-the-fly; sem signup.
  Sem auth, **o nome do tópico é essencialmente a senha** — usar sufixo aleatório e/ou ACL.
- App Android: Google Play, F-Droid ou APK do GitHub. App iOS: App Store. No app: adicionar
  servidor (URL do self-hosted) + tópico; suporta usuário/senha ou token por servidor,
  custom headers, certificados (self-signed/mTLS) e deep links `ntfy://<host>/<topic>`.
- **Instant delivery (Android)**: o flavor Google Play usa Firebase **apenas** para `ntfy.sh`;
  para self-hosted ele usa foreground service local (“instant delivery”) — necessário para
  entrega imediata com a tela apagada. O flavor F-Droid é sempre instantâneo (sem Firebase).
- **iOS + self-hosted**: entrega instantânea exige `upstream-base-url: "https://ntfy.sh"` (e
  opcionalmente `upstream-access-token`) no servidor — ele encaminha um `poll_request` ao
  ntfy.sh, que usa APNS, e o app busca a mensagem no servidor self-hosted. Sem isso, a entrega
  pode levar de 20–30 min a horas.
- Subscribe via API (para o backend, se precisar): `GET /<topic>/json` (recomendado),
  `/<topic>/sse`, `/<topic>/raw`, `/<topic>/ws`; `poll=1` e `since=` para ler cache.
  Auth igual à do publish (Basic/Bearer/`?auth=`).
- Tópicos de exemplo/protegidos em ntfy.sh (`announcements`, `stats`) são read-only para
  anônimos; servem de referência de ACL, não de configuração.

## 4. Setup mínimo Docker

Fonte: https://docs.ntfy.sh/install/#docker e https://docs.ntfy.sh/config/.

- Imagem: `binwiederhier/ntfy` (amd64, armv6, armv7, arm64); web UI + API na porta 80;
  `command: serve`.
- A imagem **não inclui** `/etc/ntfy/server.yml` — montar um arquivo ou usar env vars
  `NTFY_*`.
- Volumes: `/var/cache/ntfy` (cache de mensagens e attachments) e `/etc/ntfy` (server.yml);
  banco de auth em `/var/lib/ntfy` (a doc usa `/var/lib/ntfy/user.db` no texto e
  `/var/lib/ntfy/auth.db` no exemplo de compose — o nome é livre).
- Healthcheck oficial: `GET /v1/health` (espera `"healthy":true`).
- `behind-proxy: true` é **obrigatório** se estiver atrás de reverse proxy/TLS, senão todos os
  visitantes são rate-limited como um só (usa `X-Forwarded-For`).
- Persistência: SQLite por padrão (arquivos separados: `cache-file`, `auth-file`,
  `web-push-file`); Postgres via `database-url` (aí `cache-file`/`auth-file` não podem ser
  usados). Cache default é **em memória por 12h** e **não sobrevive a restart** — para
  persistir, definir `cache-file`.

Exemplo de compose privado (adaptado dos exemplos da doc):

```yaml
services:
  ntfy:
    image: binwiederhier/ntfy
    restart: unless-stopped
    command: serve
    environment:
      NTFY_BASE_URL: https://ntfy.example.com
      NTFY_CACHE_FILE: /var/lib/ntfy/cache.db
      NTFY_AUTH_FILE: /var/lib/ntfy/user.db
      NTFY_AUTH_DEFAULT_ACCESS: deny-all
      NTFY_AUTH_USERS: 'hablator:$2a$10$<bcrypt-hash>:admin'
      NTFY_AUTH_TOKENS: 'hablator:tk_<32-chars>:hablator-backend'
      NTFY_BEHIND_PROXY: "true"
      NTFY_ATTACHMENT_CACHE_DIR: /var/lib/ntfy/attachments
      NTFY_ENABLE_LOGIN: "true"   # opcional: login na web UI
    volumes:
      - ./data:/var/lib/ntfy
    ports:
      - 80:80
    healthcheck:
      test: ["CMD-SHELL", "wget -q --tries=1 http://localhost:80/v1/health -O - | grep -Eo '\"healthy\"\\s*:\\s*true' || exit 1"]
      interval: 60s
      timeout: 10s
      retries: 3
      start_period: 40s
    init: true
```

(Em YAML/env, `$` de hashes bcrypt precisa ser `$$` quando passado via env do compose; a doc
mostra isso no exemplo de env. Para produção, terminar TLS num reverse proxy e manter
`behind-proxy: true`.)

Config mínima equivalente em `server.yml`: `base-url`, `cache-file`, `auth-file`,
`auth-default-access: deny-all`, `auth-users`, `auth-tokens`, `behind-proxy: true`,
`attachment-cache-dir` (se anexos forem usados).

## 5. Limites relevantes

Fontes: https://docs.ntfy.sh/publish/#limitations, https://docs.ntfy.sh/config/#rate-limiting,
https://docs.ntfy.sh/config/#message-cache, https://docs.ntfy.sh/subscribe/api/#replay-limits.

| Limite | Default | Config |
|---|---|---|
| Tamanho da mensagem | 4.096 bytes (4K); maior vira attachment | `message-size-limit` (manter 4K: FCM/APNS ~4KB) |
| Título | 1 KB | — (HTTP 400 se exceder) |
| Tags combinadas | 512 bytes | — (HTTP 400 se exceder) |
| Requests por visitante | bucket de 60, refill 1 a cada 5s; HTTP 429 | `visitor-request-limit-burst`, `visitor-request-limit-replenish` |
| Mensagens/dia por visitante | governado pelo request limit por padrão | `visitor-message-daily-limit` (ntfy.sh: 250) |
| Conexões de subscription | 30 por visitante | `visitor-subscription-limit` |
| Anexo por arquivo | 15 MB (ntfy.sh: 2 MB) | `attachment-file-size-limit` |
| Anexos por visitante / total | 100 MB / 5 GB | `visitor-attachment-total-size-limit`, `attachment-total-size-limit` |
| Expiração de anexo | 3 h | `attachment-expiry-duration` |
| Banda diária por visitante | 500 MB (inclui downloads de anexo e replays de cache; HTTP 429) | `visitor-attachment-daily-bandwidth-limit` |
| Delay máximo | 3 dias | `message-delay-limit` |
| Total de tópicos | 15.000 | `global-topic-limit` |
| Criação de tópicos novos | burst 100, refill 1/min | `visitor-topic-creation-limit-*` |
| Cache de mensagens | em memória 12 h (não sobrevive restart) | `cache-duration` (0 desliga), `cache-file` persiste |
| Replay de cache | resposta capada em 10 MB por tópico (`X-Messages-Truncated: 1`) | — |
| Rate limit IPv6 | agrega por subnet /64 | `visitor-prefix-bits-ipv6` |

Pontos de atenção para a spec:

- Mensagens do hablator devem caber em 4K; payloads maiores devem virar anexo/attachment.
- O backend publicando de um único IP cai no bucket de 60 requests/refill 5s e 500 MB/dia —
  folgado para uso pessoal, mas relevante se houver retries agressivos.
- Cache em memória por default: se o telefone ficar offline e o container reiniciar, mensagens
  se perdem; definir `cache-file` para persistir e permitir `since=`/`poll=1`.
- Para iOS, incluir `upstream-base-url: https://ntfy.sh` no deploy (e token upstream se
  necessário) para push instantâneo; para Android self-hosted, habilitar “instant delivery” no
  app (ou usar o build F-Droid).
