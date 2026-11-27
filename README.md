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
