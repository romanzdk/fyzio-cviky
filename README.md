# fyzio-cviky

Připomínky fyzioterapeutických cvičení.

## Vývoj

```sh
uv sync
uv run python manage.py migrate
uv run python manage.py runserver
```

Databáze se bere z `DATABASE_URL`, výchozí je `postgres:///fyzio_cviky`.

## Testy

```sh
uv run pytest
uv run ruff check .
```

## Produkce

Nastav tyto proměnné prostředí:

- `DJANGO_DEBUG=0`
- `DJANGO_SECRET_KEY` – tajný klíč, povinný při vypnutém debugu
- `DJANGO_ALLOWED_HOSTS` – čárkou oddělené hosty
- `DJANGO_CSRF_TRUSTED_ORIGINS` – čárkou oddělené origins (např. `https://cviky.example.com`)
- `DATABASE_URL` – připojení k Postgresu
- `OPENROUTER_API_KEY` – klíč pro strukturování diktátu
- `OPENROUTER_MODEL` – název modelu
- `VAPID_PUBLIC_KEY`, `VAPID_PRIVATE_KEY` – klíče pro web push
- `VAPID_SUBJECT=mailto:<skutečná adresa>` – povinné při `DJANGO_DEBUG=0` (výchozí `mailto:admin@localhost` je povolený jen v debugu)

Pozvánku pro nového uživatele vytvoříš v administraci: `/sprava/` → „Invites“ → „Přidat“.

**Provoz, nasazení, zálohy, opravy a smazání bez AI: [docs/provoz.md](docs/provoz.md).**
