# Provoz fyzio-cviky (ruční příručka)

Tahle příručka má stačit k tomu, aby šlo appku opravit, nasadit, obnovit nebo smazat **bez AI**: jen s terminálem, SSH a prohlížečem. Všechny příkazy jsou kompletní a dají se zkopírovat.

Obsah:

1. [Co kde běží](#1-co-kde-běží)
2. [Přístupy](#2-přístupy)
3. [Nejčastější úkoly](#3-nejčastější-úkoly)
4. [Nasazení](#4-nasazení)
5. [Nastavení (.env) a klíče](#5-nastavení-env-a-klíče)
6. [Databáze: záloha a obnova](#6-databáze-záloha-a-obnova)
7. [Když něco nefunguje](#7-když-něco-nefunguje)
8. [Vazba na Vozopis (Caddy)](#8-vazba-na-vozopis-caddy)
9. [Postavení od nuly na jiném serveru](#9-postavení-od-nuly-na-jiném-serveru)
10. [Smazání celé appky](#10-smazání-celé-appky)
11. [Jak appka funguje uvnitř](#11-jak-appka-funguje-uvnitř)
12. [Lokální vývoj](#12-lokální-vývoj)

---

## 1. Co kde běží

```
iPhone (appka na ploše)
   │  HTTPS
   ▼
cviky.romanzdk.com  ── DNS v Cloudflare: A záznam → 2.29.199.192 (DNS only, ne proxy)
   │
   ▼
Hetzner VPS 2.29.199.192 (stejný server jako Vozopis)
   ├─ /opt/esk     … Vozopis: jeho Caddy drží porty 80/443 a posílá cviky.romanzdk.com dál
   └─ /opt/cviky   … tahle appka (docker compose):
        ├─ web        Django + gunicorn, port 8000, v síti "cviky" pod jménem cviky-web
        ├─ scheduler  každých 60 s spustí `python manage.py send_reminders`
        └─ db         Postgres 17, data ve volume cviky_pgdata
              │
              ├─ OpenRouter (LLM: diktát → karta cviku)
              └─ Apple Push (upozornění na iPhone)
```

| Věc | Kde |
|---|---|
| Kód | GitHub `romanzdk/fyzio-cviky` (soukromé), větev `main` |
| Image | `ghcr.io/romanzdk/fyzio-cviky:<commit>` a `:latest` (soukromý balíček na GitHubu) |
| Server | Hetzner Cloud, IP `2.29.199.192`, Ubuntu, 1 CPU, 1 GB RAM |
| Složka appky na serveru | `/opt/cviky` (vlastník uživatel `esk`) |
| Tajné hodnoty | jen na serveru v `/opt/cviky/.env` (práva 600), **nejsou v GitHubu** |
| Compose soubor | v repu `deploy/docker-compose.yml`, nasazení ho kopíruje do `/opt/cviky/` |
| HTTPS / Caddy | patří Vozopisu: repo `romanzdk/vozopis`, soubor `deploy/Caddyfile` (viz kap. 8) |
| DNS | Cloudflare, doména `romanzdk.com`, záznam `cviky` |
| Administrace | https://cviky.romanzdk.com/sprava/ |
| Kontrola, že běží | https://cviky.romanzdk.com/healthz → `ok` |
| CI / nasazení | GitHub Actions, soubor `.github/workflows/ci.yml` |
| Úkoly | GitHub issues v repu, projekt „Úkoly“ |

Hlídání: appku nic průběžně nehlídá. `/healthz` se kontroluje jen při nasazení. Healthchecks.io z Vozopisu hlídá jen Vozopis.

---

## 2. Přístupy

| Kam | Jak |
|---|---|
| Server jako běžný uživatel | `ssh esk@2.29.199.192` (Mac klíč `~/.ssh/id_ed25519`). `esk` je ve skupině `docker`. |
| Server jako root | `ssh root@2.29.199.192` (stejný klíč). Jen na věci mimo `/opt/cviky` (např. založení složky). |
| GitHub | `gh` v terminálu, nebo web. Repo nastavení: Settings → Secrets and variables → Actions. |
| Cloudflare | https://dash.cloudflare.com → přihlášení přes Google `romanzdk@gmail.com` → `romanzdk.com` → DNS → Records |
| OpenRouter | https://openrouter.ai → Settings → Keys |
| Hetzner | https://console.hetzner.com (server, firewall, snapshoty) |

GitHub Actions nastavení (repo `fyzio-cviky`):

| Název | Druh | Obsah |
|---|---|---|
| `DEPLOY_HOST` | variable | `2.29.199.192` |
| `DEPLOY_URL` | variable | `https://cviky.romanzdk.com` (bez něj se po nasazení nekontroluje `/healthz`) |
| `DEPLOY_SSH_KEY` | secret | soukromý SSH klíč; veřejná půlka je v `/home/esk/.ssh/authorized_keys` s komentářem `fyzio-cviky deploy` |
| `DEPLOY_KNOWN_HOSTS` | secret | výstup `ssh-keyscan -t ed25519 2.29.199.192` |

---

## 3. Nejčastější úkoly

Skoro všechno se dělá na serveru ve složce appky:

```bash
ssh esk@2.29.199.192
cd /opt/cviky
```

### Stav a logy

```bash
docker compose ps                         # běží db, web, scheduler?
docker compose logs --tail 100 web        # chyby webu
docker compose logs -f scheduler          # připomínky; každou minutu "Odesláno: N"
curl -s https://cviky.romanzdk.com/healthz   # má vrátit: ok
free -m; df -h /                          # paměť a disk serveru
```

### Restart

```bash
docker compose restart web scheduler      # jen appka
docker compose up -d                      # spustí, co neběží (po rebootu se spustí samo: restart: unless-stopped)
```

### Pozvat nového uživatele

1. Přihlas se na https://cviky.romanzdk.com/sprava/ (účet s právem správce).
2. V sekci „Cviky“ → „Invites“ → „Přidat“ → „Uložit“ (názvy tabulek jsou v administraci anglicky).
3. Ve sloupci „Registrační odkaz“ zkopíruj odkaz a pošli ho. Jeden odkaz = jedna registrace.

Bez administrace, přímo na serveru:

```bash
docker compose exec -T web python manage.py shell -c "from cviky.models import Invite; print('https://cviky.romanzdk.com/registrace/%s/' % Invite.objects.create().token)"
```

### Udělat z uživatele správce

```bash
docker compose exec -T web python manage.py shell -c "from cviky.models import User; User.objects.filter(username='JMENO').update(is_staff=True, is_superuser=True)"
```

Nový správce úplně od nuly (zeptá se na jméno a heslo):

```bash
docker compose exec web python manage.py createsuperuser
```

### Zapomenuté heslo

```bash
docker compose exec web python manage.py changepassword JMENO
```

### Smazat uživatele (i se všemi jeho cviky, sériemi a odběry)

V administraci: „Users“ → uživatel → „Odstranit“. Nebo:

```bash
docker compose exec -T web python manage.py shell -c "from cviky.models import User; print(User.objects.filter(username='JMENO').delete())"
```

### Ručně poslat připomínky hned

```bash
docker compose exec scheduler python manage.py send_reminders
```

Pošle jen série, které jsou právě „na řadě“ (viz kap. 11). Každá série nejvýš jednou za den.

---

## 4. Nasazení

### Normálně (automaticky)

Každý push do `main` spustí `.github/workflows/ci.yml`:

1. **test**: ruff, kontrola migrací, pytest proti Postgresu.
2. **image**: postaví Docker image a nahraje ho do GHCR jako `:<commit>` a `:latest`.
3. **deploy**: přes SSH jako `esk` nakopíruje `deploy/docker-compose.yml` do `/opt/cviky/`, přihlásí se do GHCR, stáhne image, spustí `docker compose up -d` a zkontroluje `/healthz`.

Migrace databáze se spustí samy při startu kontejneru `web` (`python manage.py migrate`).

Stav: `gh run list -R romanzdk/fyzio-cviky` nebo záložka Actions na GitHubu. Znovu spustit: na GitHubu „Re-run jobs“, nebo `gh workflow run CI -R romanzdk/fyzio-cviky --ref main`.

### Ručně, když GitHub Actions nejdou

Image je soukromý, takže server se musí do GHCR přihlásit. Potřebuješ GitHub token s právem `read:packages` (GitHub → Settings → Developer settings → Personal access tokens).

```bash
ssh esk@2.29.199.192
cd /opt/cviky
echo TOKEN | docker login ghcr.io -u romanzdk --password-stdin
CVIKY_IMAGE=ghcr.io/romanzdk/fyzio-cviky:latest docker compose pull web
CVIKY_IMAGE=ghcr.io/romanzdk/fyzio-cviky:latest docker compose up -d
docker logout ghcr.io
```

Když se změnil `deploy/docker-compose.yml`, nejdřív ho nakopíruj z Macu: `scp deploy/docker-compose.yml esk@2.29.199.192:/opt/cviky/`.

### Ručně, když nejde ani GHCR (postavit image přímo na serveru)

Pomalé (1 CPU), ale funguje bez GitHubu:

```bash
# na Macu
cd ~/Repos/fyzio-cviky && git archive -o /tmp/cviky.tar.gz HEAD && scp /tmp/cviky.tar.gz esk@2.29.199.192:/tmp/
# na serveru
mkdir -p /tmp/cviky-src && tar -xzf /tmp/cviky.tar.gz -C /tmp/cviky-src
docker build -t ghcr.io/romanzdk/fyzio-cviky:latest /tmp/cviky-src
cd /opt/cviky && docker compose up -d
```

### Návrat na starší verzi

Každý image má tag podle commitu. Seznam commitů: `git log --oneline` nebo GitHub. Pozor: když novější verze přidala migraci databáze, starší kód s ní nemusí fungovat. Pak nejdřív obnov zálohu (kap. 6).

```bash
cd /opt/cviky
echo TOKEN | docker login ghcr.io -u romanzdk --password-stdin
CVIKY_IMAGE=ghcr.io/romanzdk/fyzio-cviky:<celý-sha-commitu> docker compose up -d
docker logout ghcr.io
```

Pozor: příští automatické nasazení zase nasadí nejnovější `main`. Trvalý návrat = `git revert` v repu a push.

Pozor 2: nasazení Vozopisu na konci maže nepoužívané Docker image (`docker image prune -af`). Starší image fyzio-cviky na serveru tedy nebývají. Stáhnou se znovu z GHCR.

---

## 5. Nastavení (.env) a klíče

Soubor `/opt/cviky/.env` (práva 600). Čte ho `db`, `web` i `scheduler`. `DJANGO_DEBUG=0`, `DJANGO_ALLOWED_HOSTS` a `DJANGO_CSRF_TRUSTED_ORIGINS` jsou přímo v `deploy/docker-compose.yml`.

| Proměnná | K čemu | Jak získat nový |
|---|---|---|
| `POSTGRES_USER`, `POSTGRES_DB` | jméno uživatele a databáze (`cviky`) | — |
| `POSTGRES_PASSWORD` | heslo databáze | `openssl rand -hex 32`. Pozor: Postgres si heslo pamatuje z prvního startu, změna v `.env` nestačí, viz níže. |
| `DATABASE_URL` | `postgres://cviky:<heslo>@db:5432/cviky` | složit z hodnot výše |
| `DJANGO_SECRET_KEY` | podpis přihlášení | `openssl rand -hex 32`. Změna odhlásí všechny. |
| `OPENROUTER_API_KEY` | LLM | openrouter.ai → Settings → Keys → Create. Teď se používá klíč sdílený s ai-newsletterem (limit 20 USD). |
| `OPENROUTER_MODEL` | model, teď `deepseek/deepseek-v4.1-flash` | libovolný model z openrouter.ai/models, který umí „structured outputs“ |
| `VAPID_PUBLIC_KEY`, `VAPID_PRIVATE_KEY` | podpis push upozornění | viz níže. Změna = všichni musí znovu zapnout upozornění. |
| `VAPID_SUBJECT` | kontakt pro Apple, `mailto:romanzdk@gmail.com` | skutečná adresa, jinak Apple upozornění odmítá a appka při startu spadne |

Úprava:

```bash
ssh esk@2.29.199.192
cd /opt/cviky
nano .env                                  # nebo vi
docker compose up -d                       # přenačte .env (kontejnery se vymění)
```

### Nové VAPID klíče

Na Macu v repu:

```bash
cd ~/Repos/fyzio-cviky
uv run python -c "
from py_vapid import Vapid01, b64urlencode
from cryptography.hazmat.primitives import serialization as s
v=Vapid01(); v.generate_keys()
print('VAPID_PUBLIC_KEY='+b64urlencode(v.public_key.public_bytes(s.Encoding.X962, s.PublicFormat.UncompressedPoint)))
print('VAPID_PRIVATE_KEY='+b64urlencode(v.private_key.private_numbers().private_value.to_bytes(32,'big')))"
```

Oba řádky přepiš v `.env` a dej `docker compose up -d`. Staré odběry pak nefungují. Smaž je, aby se zbytečně neposílaly:

```bash
docker compose exec -T web python manage.py shell -c "from cviky.models import PushSubscription; print(PushSubscription.objects.all().delete())"
```

Potom každý na iPhonu otevře appku z plochy → Profil → Upozornění → „Zapnout upozornění“.

### Změna hesla databáze

```bash
cd /opt/cviky
docker compose exec db psql -U cviky -d cviky -c "ALTER USER cviky PASSWORD 'NOVE_HESLO';"
nano .env        # přepiš POSTGRES_PASSWORD i heslo v DATABASE_URL
docker compose up -d
```

### Nový SSH klíč pro nasazování

```bash
ssh-keygen -t ed25519 -N "" -C "fyzio-cviky deploy" -f /tmp/deploy_key
ssh esk@2.29.199.192 'cat >> ~/.ssh/authorized_keys' < /tmp/deploy_key.pub
gh secret set DEPLOY_SSH_KEY -R romanzdk/fyzio-cviky < /tmp/deploy_key
rm /tmp/deploy_key /tmp/deploy_key.pub
# starý klíč na serveru smaž: v ~/.ssh/authorized_keys řádek s komentářem "fyzio-cviky deploy" (ten starší)
```

---

## 6. Databáze: záloha a obnova

**Automatická záloha zatím není nastavená.** Data jsou jen ve volume `cviky_pgdata` na serveru. Když server zmizí, zmizí i data. (Vozopis má vlastní `backup.sh`, ta zálohuje jen Vozopis.)

### Ruční záloha

```bash
ssh esk@2.29.199.192
cd /opt/cviky
docker compose exec -T db pg_dump -U cviky cviky | gzip > ~/cviky-$(date +%F).sql.gz
# stáhnout na Mac:
exit
scp esk@2.29.199.192:~/cviky-*.sql.gz ~/Downloads/
```

### Obnova ze zálohy

Přepíše současná data.

```bash
scp ~/Downloads/cviky-2026-11-27.sql.gz esk@2.29.199.192:~/
ssh esk@2.29.199.192
cd /opt/cviky
docker compose stop web scheduler
docker compose exec -T db psql -U cviky -d postgres -c "DROP DATABASE cviky;" -c "CREATE DATABASE cviky OWNER cviky;"
gunzip -c ~/cviky-2026-11-27.sql.gz | docker compose exec -T db psql -U cviky -d cviky -q
docker compose start web scheduler
```

### Přímý přístup do databáze

```bash
docker compose exec db psql -U cviky cviky
# užitečné: \dt (tabulky), SELECT username FROM cviky_user;, \q (konec)
```

Tabulky: `cviky_user`, `cviky_invite`, `cviky_exercise`, `cviky_series`, `cviky_seriesexercise`, `cviky_completion`, `cviky_pushsubscription`, `cviky_remindersent`.

---

## 7. Když něco nefunguje

Vždycky začni tímhle:

```bash
ssh esk@2.29.199.192 'cd /opt/cviky && docker compose ps && docker compose logs --tail 50 web'
curl -sI https://cviky.romanzdk.com/healthz
```

| Příznak | Pravděpodobná příčina | Co udělat |
|---|---|---|
| Stránka vrací **502** | `web` neběží nebo Caddy na něj nevidí | `docker compose ps`; když `web` neběží: `docker compose logs web` a `docker compose up -d`. Když běží: zkontroluj kap. 8 (síť `cviky`, blok v Caddyfile). |
| `web` hned spadne, v logu `RuntimeError: ... must be set` | chybí `DJANGO_SECRET_KEY` nebo `VAPID_SUBJECT` v `.env` | doplň `.env` (kap. 5), `docker compose up -d` |
| `web` spadne na databázi | `db` neběží nebo nesedí heslo | `docker compose logs db`; heslo v `DATABASE_URL` = `POSTGRES_PASSWORD` |
| Certifikát / HTTPS nejde | DNS neukazuje na server, nebo je záznam v Cloudflare „Proxied“ | `dig +short cviky.romanzdk.com` musí vrátit `2.29.199.192`. V Cloudflare přepni na „DNS only“. Logy: `cd /opt/esk && docker compose logs --tail 100 caddy`. |
| Po nasazení **Vozopisu** přestala appka jít | někdo z Vozopis repa smazal blok `cviky.romanzdk.com` nebo síť `cviky` | kap. 8 |
| Diktát vytvoří **prázdnou kartu** s poznámkou „Automatické zpracování se nepovedlo“ | LLM selhalo (klíč, kredit, model, výpadek) | `docker compose logs web \| grep -i openrouter`; kredit na openrouter.ai; zkus klíč: `curl -s -H "Authorization: Bearer KLIC" https://openrouter.ai/api/v1/key`. Karta jde mezitím vyplnit ručně. |
| **Upozornění nechodí** | appka není přidaná na plochu, upozornění nejsou zapnutá, série nemá dny/čas, nebo Apple odmítá | 1) na iPhonu otevřít appku **z plochy** → Profil → Upozornění → Zapnout. 2) v administraci „Push subscriptions“ musí být řádek pro uživatele. 3) série musí mít vybraný den a čas. 4) `docker compose logs scheduler` hledej `Push failed`. 403 = špatné VAPID klíče nebo `VAPID_SUBJECT`. |
| Upozornění přišlo dvakrát / nepřišlo dnes | — | každá série max. 1× denně (tabulka `cviky_remindersent`). Pro test smaž dnešní řádek: `docker compose exec -T web python manage.py shell -c "from cviky.models import ReminderSent; ReminderSent.objects.all().delete()"` |
| Plánovač v logu `send_reminders failed` | chyba v kódu nebo DB | vypíše se traceback nad tím řádkem; smyčka běží dál a zkusí to za minutu |
| Dochází paměť (server má 1 GB) | moc procesů | `free -m`, `docker stats --no-stream`. Limity jsou v `deploy/docker-compose.yml` (`mem_limit`). Snížit počet workerů: do `.env` přidat `WEB_CONCURRENCY=1`. |
| Plný disk | logy/image | `docker system df`; `docker image prune -af` (smaže nepoužívané image, data ne) |
| Přihlášení v appce na ploše pořád padá | smazané cookies na iPhonu | přihlásit znovu; přihlášení vydrží rok |

---

## 8. Vazba na Vozopis (Caddy)

Porty 80/443 na serveru drží Caddy z Vozopisu. Proto:

- V repu **`romanzdk/vozopis`** je v `deploy/Caddyfile` blok:
  ```
  cviky.romanzdk.com {
  	encode zstd gzip
  	header Strict-Transport-Security "max-age=31536000"
  	header X-Robots-Tag "noindex, nofollow"
  	reverse_proxy cviky-web:8000
  }
  ```
- V `deploy/docker-compose.yml` Vozopisu je služba `caddy` připojená i k externí síti `cviky`.
- Obě nasazení (Vozopis i fyzio-cviky) síť `cviky` vytvoří, když chybí (`docker network create cviky`).
- **Ruční úprava Caddyfile přímo na serveru se při příštím nasazení Vozopisu přepíše.** Měň ho vždy v repu Vozopis.

Ruční oprava, když blok nebo síť zmizí:

```bash
ssh esk@2.29.199.192
docker network inspect cviky >/dev/null 2>&1 || docker network create cviky
cd /opt/esk
grep -n cviky Caddyfile docker-compose.yml     # musí najít blok i síť
docker compose up -d caddy                     # po změně compose
docker compose restart caddy                   # po změně Caddyfile
```

### Když by se Vozopis odstěhoval nebo vypnul

Appka pak potřebuje vlastní Caddy. Do `deploy/docker-compose.yml` fyzio-cviky přidej:

```yaml
  caddy:
    image: caddy:2.11.9
    restart: unless-stopped
    ports: ["80:80", "443:443"]
    volumes:
      - ./Caddyfile:/etc/caddy/Caddyfile:ro
      - caddy_data:/data
    networks: [cviky]
```

do `volumes:` přidej `caddy_data:` a vedle compose dej `/opt/cviky/Caddyfile` se stejným blokem jako výše. Porty 80/443 musí být volné (Caddy Vozopisu vypnutý).

---

## 9. Postavení od nuly na jiném serveru

Předpoklad: Ubuntu server s Dockerem a uživatelem ve skupině `docker`.

1. **Složka a síť** (na serveru jako root):
   ```bash
   install -d -o esk -g esk -m 750 /opt/cviky
   docker network create cviky
   ```
2. **`.env`** (jako `esk`): vytvoř `/opt/cviky/.env` s hodnotami z kap. 5, pak `chmod 600 /opt/cviky/.env`. Vzor:
   ```
   POSTGRES_USER=cviky
   POSTGRES_PASSWORD=<openssl rand -hex 32>
   POSTGRES_DB=cviky
   DATABASE_URL=postgres://cviky:<stejné heslo>@db:5432/cviky
   DJANGO_SECRET_KEY=<openssl rand -hex 32>
   OPENROUTER_API_KEY=sk-or-v1-...
   OPENROUTER_MODEL=deepseek/deepseek-v4.1-flash
   VAPID_PUBLIC_KEY=<kap. 5>
   VAPID_PRIVATE_KEY=<kap. 5>
   VAPID_SUBJECT=mailto:romanzdk@gmail.com
   ```
3. **Caddy**: buď blok v Caddy Vozopisu (kap. 8), nebo vlastní Caddy (kap. 8, poslední část).
4. **DNS**: v Cloudflare změň A záznam `cviky` na novou IP, **DNS only**.
5. **GitHub**: `gh variable set DEPLOY_HOST -R romanzdk/fyzio-cviky --body <nová IP>`, nový `DEPLOY_KNOWN_HOSTS` (`ssh-keyscan -t ed25519 <IP> | gh secret set DEPLOY_KNOWN_HOSTS -R romanzdk/fyzio-cviky`) a SSH klíč (kap. 5).
6. **Nasadit**: `gh workflow run CI -R romanzdk/fyzio-cviky --ref main`, nebo ručně (kap. 4).
7. **Data**: obnov zálohu (kap. 6).
8. **Ověřit**: `curl https://cviky.romanzdk.com/healthz` → `ok`; přihlásit se; na iPhonu zapnout upozornění (nový server = stejné VAPID klíče → odběry fungují dál, jen když jsi klíče přenesl).

---

## 10. Smazání celé appky

Nevratné. Nejdřív záloha (kap. 6), pokud data chceš.

1. **Kontejnery a data** na serveru:
   ```bash
   ssh esk@2.29.199.192
   cd /opt/cviky
   docker compose down -v          # -v smaže i databázi (volume cviky_pgdata)
   ```
   Složku `/opt/cviky` pak smaž jako root (`ssh root@2.29.199.192` a odstranit složku `/opt/cviky`).
2. **Caddy a síť ve Vozopisu**: v repu `romanzdk/vozopis` smaž blok `cviky.romanzdk.com` z `deploy/Caddyfile`, síť `cviky` u služby `caddy` a v sekci `networks` v `deploy/docker-compose.yml` a řádek `docker network inspect cviky ... || docker network create cviky` v `.github/workflows/ci.yml`. Commit + push → nasadí se samo. Pak na serveru `docker network rm cviky`.
3. **DNS**: v Cloudflare smaž A záznam `cviky`.
4. **SSH klíč**: na serveru v `/home/esk/.ssh/authorized_keys` smaž řádek `fyzio-cviky deploy`.
5. **GitHub**: balíček GHCR smaž na github.com → profil → Packages → `fyzio-cviky` → Package settings → Delete. Repo archivuj nebo smaž (`gh repo archive romanzdk/fyzio-cviky`).
6. **OpenRouter**: pokud appka měla vlastní klíč, smaž ho na openrouter.ai → Settings → Keys.
7. **Přehled projektů**: smaž záznam „Fyzio cviky“ v `~/Repos/prehled-projektu/projects.yaml`, commit, `./deploy.sh`.

---

## 11. Jak appka funguje uvnitř

### Soubory

| Soubor | Co dělá |
|---|---|
| `config/settings.py` | nastavení z proměnných prostředí, časová zóna `Europe/Prague` |
| `config/urls.py` | všechny adresy |
| `cviky/models.py` | databázové tabulky (viz níže) |
| `cviky/choices.py` | pevné seznamy oblastí, poloh a dnů |
| `cviky/llm.py` | volání OpenRouteru: text → `ExerciseDraft`; při chybě vrátí prázdný návrh, nikdy nespadne |
| `cviky/today.py` | výpočty pro „Dnes“: dnešní série, co je odkliknuté, „Dlouho jsi nedělal“ |
| `cviky/reminders.py` | kdy poslat připomínku, text upozornění, odeslání přes Web Push |
| `cviky/management/commands/send_reminders.py` | příkaz, který spouští plánovač |
| `cviky/views/*.py` | stránky: `auth` (registrace), `exercises`, `series`, `today`, `profile`, `push` (PWA a odběr), `health` |
| `cviky/templates/` | HTML šablony (`base.html` = hlavička, spodní lišta a tlačítko „Nadiktovat cvik“; `cviky/check_button.html` = kulaté odškrtávátko) |
| `cviky/static/cviky/app.css` | celý vzhled appky (barvy nahoře v `:root`, tmavý režim v `@media (prefers-color-scheme: dark)`) |
| `cviky/static/cviky/icon.svg` | ikona appky; PNG verze (`icon-192.png`, `icon-512.png`, `apple-touch-icon.png`) jsou z ní vykreslené |
| `cviky/static/sw.js` | service worker: zobrazí upozornění a po klepnutí otevře appku |
| `cviky/static/manifest.webmanifest` | údaje pro „Přidat na plochu“ |
| `cviky/static/cviky/push.js` | tlačítko „Zapnout upozornění“ |
| `cviky/static/cviky/body/*.svg`, `poloha/*.svg` | ikonky oblasti těla a polohy |
| `tests/` | testy (pytest) |

### Tabulky

- **User**: uživatel; `neglect_days` = po kolika dnech je cvik „dlouho nedělaný“ (výchozí 7).
- **Invite**: pozvánka; `used_at` vyplněné = použitá.
- **Exercise**: karta cviku (název, oblast, poloha, štítky, kroky, na co dát pozor, opakování, původní text diktátu).
- **Series** + **SeriesExercise**: série (dny 0 = pondělí … 6 = neděle, čas připomínky) a pořadí cviků v ní.
- **Completion**: odkliknutí cviku (kdy, případně v jaké sérii).
- **PushSubscription**: odběr upozornění jednoho telefonu.
- **ReminderSent**: že série dnes už dostala připomínku.

### Diktát → karta

1. `/cviky/novy/` → uživatel diktuje do textového pole (mikrofon v klávesnici iPhonu).
2. Server pošle text na OpenRouter (`cviky/llm.py`) s pevným JSON schématem a `provider: {zdr: true, data_collection: deny}`. Limit 20 s.
3. Uživatel vidí předvyplněnou kartu a původní text, upraví ji a uloží.
4. Když LLM selže, název se předvyplní ze začátku diktátu a zbytek se vyplní ručně.

### Připomínky

Plánovač každých 60 s spustí `send_reminders`. Série dostane připomínku, když:

- má nastavený čas a dnešní den v týdnu,
- je teď mezi časem připomínky a +60 minut (do půlnoci), takže restart serveru připomínku neztratí,
- má aspoň jeden cvik a ne všechny jsou dnes odkliknuté,
- ještě dnes nedostala připomínku (`ReminderSent`).

Text: název série a „4 cviky + 2 dlouho nedělané“. Odběry, které Apple hlásí jako zaniklé (404/410), se smažou.

### „Dlouho jsi nedělal“

Cvik, který je v nějaké sérii a nebyl odkliknutý aspoň `neglect_days` dní. Když nebyl odkliknutý nikdy, počítá se od přidání do série.

---

## 12. Lokální vývoj

Na Macu: Postgres z Homebrew (`brew services start postgresql@18`, databáze `createdb fyzio_cviky`) a `uv`.

```bash
cd ~/Repos/fyzio-cviky
uv sync
uv run python manage.py migrate
uv run python manage.py createsuperuser
uv run python manage.py runserver          # http://localhost:8000
uv run pytest -q                           # testy
uv run ruff check .                        # kontrola kódu
```

Bez `OPENROUTER_API_KEY` diktát vždy vrátí prázdnou kartu, bez `VAPID_*` se upozornění neposílají. Pro vyzkoušení LLM lokálně: `OPENROUTER_API_KEY=... OPENROUTER_MODEL=deepseek/deepseek-v4.1-flash uv run python manage.py runserver`.

Návrh a plán v1: `docs/superpowers/specs/` a `docs/superpowers/plans/`.
