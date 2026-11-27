# Fyzio cviky v1 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** A Czech mobile web app (PWA on iPhone) where a user dictates a physio exercise, an LLM turns it into an exercise card, cards go into series, and the app reminds the user daily and surfaces exercises not done for a while.

**Architecture:** One Django project with one app `cviky` (server-rendered templates, minimal JS: service worker + push subscribe). Postgres. A second container runs `manage.py send_reminders` every 60 s. Deployed next to Vozopis on the same Hetzner VPS behind its Caddy, at `cviky.romanzdk.com`.

**Tech Stack:** Python + Django + Postgres (`django.contrib.postgres`, `unaccent`), pytest-django, httpx (OpenRouter), pywebpush (Web Push/VAPID), Docker Compose, Caddy, GitHub Actions + GHCR + SSH deploy. Versions, tooling (Poetry/uv), lint config, Dockerfile and CI: copy from `romanzdk/vozopis`.

**Spec:** `docs/superpowers/specs/2026-11-27-fyzio-cviky-design.md`

## Global Constraints

- All UI text in Czech. Code identifiers in English.
- `TIME_ZONE = "Europe/Prague"`, `USE_TZ = True`. "Today" always means the Prague calendar date.
- Areas (`Exercise.area` choices, exact order): `krk` krk, `ramena` ramena, `hrudni` hrudní páteř, `bederni` bederní páteř, `panev` pánev/kyčle, `kolena` kolena, `kotniky` kotníky/chodidla, `ruce` zápěstí/ruce, `cele_telo` celé tělo.
- Positions (`Exercise.position` choices): `sed` sed, `stoj` stoj, `leh_zada` leh na zádech, `leh_bricho` leh na břiše, `leh_bok` leh na boku, `ctyri` na čtyřech.
- No open registration: accounts only via one-time invite link created in Django admin.
- Every user sees and changes only their own data; another user's object ID → 404.
- LLM only via OpenRouter with `provider: {"zdr": true, "data_collection": "deny"}`; API key only on the server (`OPENROUTER_API_KEY`). Model in `OPENROUTER_MODEL` env.
- One dictation = one exercise. Original text is always saved.
- No AI-generated images. Illustration = body outline with highlighted area + position icon (SVG).
- Neglect threshold default 7 days, per-user setting.
- Must not disturb Vozopis: own containers, own Postgres container/volume, memory limits in compose.
- iPhone: push only works for the app added to Home Screen (iOS 16.4+).

## Review Focus

1. Day boundaries in Prague time: a check-off at 23:30 Prague (22:30 UTC) belongs to that day; DST switch days still fire reminders once. → Task 6 and Task 8 tests.
2. LLM failure: timeout, non-JSON, area/position outside the lists, missing fields → card still saves with the original text and empty fields. → Task 3 tests.
3. Expired push subscription (404/410 from push service) → subscription deleted, other subscriptions still get the push, the loop does not crash. → Task 8 test.
4. Scheduler restart or a skipped minute → a reminder is sent at most once per series per day, and a reminder missed by ≤ 60 min is still sent. → Task 8 tests.
5. Accessing another user's exercise/series/completion by ID → 404. → Task 4 and Task 5 tests.

---

### Task 1: Project skeleton

**Files:**
- Create: repo `romanzdk/fyzio-cviky` (private) in `~/Repos/fyzio-cviky`; Django project `config/`, app `cviky/`, `pyproject.toml`, `docker-compose.yml` (dev: `db` only), `tests/test_health.py`
- Move: spec + this plan into `docs/superpowers/specs/` and `docs/superpowers/plans/`
- Reference: clone `romanzdk/vozopis` to `~/Repos/vozopis` and copy its tooling/settings layout

**Interfaces:**
- Produces: custom user `cviky.User(AbstractUser)` with `neglect_days: PositiveSmallIntegerField(default=7)`; `AUTH_USER_MODEL = "cviky.User"`; URL `/healthz` → `200 "ok"`; migration enabling `UnaccentExtension()`.

- [ ] **Step 1:** Write `test_healthz_ok`: `client.get("/healthz")` → status 200, body `b"ok"`.
- [ ] **Step 2:** Run `pytest tests/test_health.py` → FAIL (404).
- [ ] **Step 3:** Create the project, settings from env (`SECRET_KEY`, `DATABASE_URL`, `ALLOWED_HOSTS`), user model, `UnaccentExtension` migration, `/healthz` view.
- [ ] **Step 4:** Run `pytest` → PASS.
- [ ] **Step 5:** Commit `chore: project skeleton`.

### Task 2: Invites and login

**Files:**
- Create: `cviky/models.py` (`Invite`), `cviky/admin.py`, `cviky/views/auth.py`, templates `registration/login.html`, `cviky/register.html`, `tests/test_auth.py`

**Interfaces:**
- Produces: `Invite(token: UUID default uuid4, created_at, used_by: FK User null, used_at null)`; admin shows the full link `https://<host>/registrace/<token>/`; URLs `/prihlaseni/`, `/odhlaseni/`, `/registrace/<uuid:token>/`; all app views require login (`LOGIN_URL="/prihlaseni/"`).

- [ ] **Step 1:** Tests:
  - `test_register_with_valid_invite_creates_user_and_marks_used`: POST username+password1+password2 → user exists, logged in, `invite.used_by == user`.
  - `test_used_invite_returns_404`, `test_unknown_token_returns_404`.
  - `test_no_open_registration`: no URL creates a user without a token.
  - `test_anonymous_redirected_to_login`: GET `/` → 302 to `/prihlaseni/?next=/`.
- [ ] **Step 2:** Run → FAIL.
- [ ] **Step 3:** Implement with Django `UserCreationForm` and `LoginView`/`LogoutView`. Mark the invite used in the same transaction (`select_for_update`).
- [ ] **Step 4:** Run → PASS.
- [ ] **Step 5:** Commit `feat: invite-only registration`.

### Task 3: LLM structuring

**Files:**
- Create: `cviky/llm.py`, `tests/test_llm.py`

**Interfaces:**
- Produces:
  ```python
  @dataclass
  class ExerciseDraft:
      title: str = ""
      area: str = ""          # one of AREA keys or ""
      position: str = ""      # one of POSITION keys or ""
      tags: list[str] = field(default_factory=list)  # incl. synonyms, lowercase
      steps: str = ""         # one step per line
      cautions: str = ""
      reps: str = ""          # e.g. "10× na každou stranu", may be ""
  def structure_exercise(text: str) -> ExerciseDraft  # never raises
  ```
  `AREAS` and `POSITIONS` choice tuples live in `cviky/choices.py` (used by models in Task 4).

- [ ] **Step 1:** Tests (mock `httpx.post` with `monkeypatch`):
  - `test_valid_response_maps_fields`: LLM returns JSON with `area="krk"`, `position="sed"` → draft has those values and tags list.
  - `test_unknown_area_becomes_empty`: `area="hlava"` → `draft.area == ""`, other fields kept.
  - `test_non_json_returns_empty_draft`, `test_timeout_returns_empty_draft`, `test_http_500_returns_empty_draft`.
  - `test_request_sends_zdr_and_deny`: captured payload has `provider == {"zdr": True, "data_collection": "deny"}` and `response_format.type == "json_schema"`.
- [ ] **Step 2:** Run → FAIL.
- [ ] **Step 3:** Implement: POST `https://openrouter.ai/api/v1/chat/completions`, timeout 30 s, Czech system prompt that lists the allowed area/position keys and asks for 3–8 tags incl. synonyms (e.g. krk → krční páteř, šíje). Log errors, return `ExerciseDraft()`.
- [ ] **Step 4:** Run → PASS.
- [ ] **Step 5:** Commit `feat: LLM exercise structuring`.

### Task 4: Exercises – dictate, review, list, search

**Files:**
- Create: `cviky/choices.py` (if not in Task 3), `cviky/forms.py`, `cviky/views/exercises.py`, templates `cviky/exercise_*.html`, `cviky/ilustrace.html`, `static/cviky/body/*.svg`, `static/cviky/poloha/*.svg`, `tests/test_exercises.py`
- Modify: `cviky/models.py`

**Interfaces:**
- Consumes: `structure_exercise`, `ExerciseDraft`.
- Produces: `Exercise(user FK, title, area choices blank, position choices blank, tags ArrayField(CharField), steps Text, cautions Text, reps Char, original_text Text, created_at)`; URLs `/cviky/` (list+search), `/cviky/novy/` (dictate), `/cviky/<id>/`, `/cviky/<id>/upravit/`, `/cviky/<id>/smazat/`; helper `search_exercises(user, q: str, area: str = "", position: str = "") -> QuerySet[Exercise]`; template include `{% include "cviky/ilustrace.html" with area=e.area position=e.position %}`.

- [ ] **Step 1:** Tests:
  - `test_dictate_shows_prefilled_form`: POST text to `/cviky/novy/` (LLM mocked) → response contains the draft title; nothing saved yet.
  - `test_save_keeps_original_text`; `test_llm_failure_still_allows_save` (empty draft → form with `original_text` filled, title required → user types it).
  - `test_empty_text_rejected`, `test_text_over_5000_chars_rejected`.
  - `test_search_ignores_diacritics`: exercise "Uvolnění krční páteře", `q="pater"` → found.
  - `test_search_matches_tags`: tag "šíje", `q="sije"` → found.
  - `test_filters_area_and_position`.
  - `test_other_users_exercise_404` for detail, edit, delete.
  - `test_illustration_renders_for_every_area_and_position`.
  - After save, page shows button "Přidat další cvik" → `/cviky/novy/`.
- [ ] **Step 2:** Run → FAIL.
- [ ] **Step 3:** Implement. Search: split `q` into words; each word must match `title__unaccent__icontains` OR `steps__unaccent__icontains` OR `original_text__unaccent__icontains` OR any tag (unaccented). `# ponytail: icontains scan, per-user data is small; switch to SearchVector + GIN if one user has thousands`. Textarea gets `autofocus` and a hint "Klepni na mikrofon na klávesnici a diktuj".
- [ ] **Step 4:** Run → PASS.
- [ ] **Step 5:** Commit `feat: exercises with dictation and search`.

### Task 5: Series

**Files:**
- Create: `cviky/views/series.py`, templates `cviky/series_*.html`, `tests/test_series.py`
- Modify: `cviky/models.py`, `cviky/forms.py`

**Interfaces:**
- Produces: `Series(user FK, name, weekdays ArrayField(PositiveSmallIntegerField) # 0=Mon..6=Sun, remind_at TimeField null)`; `SeriesExercise(series FK, exercise FK, order int, added_at datetime auto)` unique `(series, exercise)`, ordered by `order`; URLs `/serie/`, `/serie/nova/`, `/serie/<id>/upravit/`, `/serie/<id>/smazat/`. Exercise list filter `serie=<id>` added to `search_exercises(..., series_id: int | None = None)`.

- [ ] **Step 1:** Tests: create series with days [0,2,4], time 07:30, three exercises in given order → stored order preserved; form only offers own exercises; `test_other_users_series_404`; removing an exercise from a series keeps the exercise; re-adding resets `added_at`.
- [ ] **Step 2:** Run → FAIL.
- [ ] **Step 3:** Implement (day checkboxes Po–Ne, `<input type="time">`, order via number inputs).
- [ ] **Step 4:** Run → PASS.
- [ ] **Step 5:** Commit `feat: series`.

### Task 6: Today screen, check-off, neglected

**Files:**
- Create: `cviky/today.py`, `cviky/views/today.py`, template `cviky/today.html`, `tests/test_today.py`
- Modify: `cviky/models.py`, profile page for `neglect_days`

**Interfaces:**
- Produces: `Completion(user FK, exercise FK, series FK null, done_at datetime default now)`;
  ```python
  def local_date(dt: datetime) -> date                      # Prague date
  def todays_series(user, today: date) -> list[Series]       # today.weekday() in weekdays
  def done_today(user, series: Series, today: date) -> set[int]   # exercise ids checked for this series today
  def neglected(user, now: datetime) -> list[tuple[Exercise, int]]  # (exercise, days since last done), oldest first
  ```
  `neglected`: exercises in any of the user's series; reference time = last `Completion.done_at`, else earliest `SeriesExercise.added_at`; included when `(local_date(now) - local_date(ref)).days >= user.neglect_days`.
  URLs: `/` = today; POST `/hotovo/` (`exercise`, `series` optional) toggles today's completion for that series; `/profil/` edits `neglect_days` (1–60).

- [ ] **Step 1:** Tests:
  - `test_today_lists_series_for_weekday_only`.
  - `test_check_off_and_undo` (toggle twice → no completion today).
  - `test_completion_at_2330_prague_counts_for_that_day` (UTC 22:30 in winter).
  - `test_neglected_after_7_days`: last done 7 days ago → listed with 7; 6 days → not listed.
  - `test_never_done_counts_from_added_at`.
  - `test_neglect_days_setting_respected` (set 3).
  - `test_other_users_exercise_cannot_be_checked` → 404.
  - Page shows "Dlouho jsi nedělal" section only when the list is non-empty; each row has "(N dní)".
- [ ] **Step 2:** Run → FAIL.
- [ ] **Step 3:** Implement; layout per spec sketch (series with `x/y ✓`, checkboxes as POST buttons, neglected section, button "Nadiktovat nový cvik").
- [ ] **Step 4:** Run → PASS.
- [ ] **Step 5:** Commit `feat: today screen and neglected exercises`.

### Task 7: PWA and push subscription

**Files:**
- Create: `static/manifest.webmanifest`, `static/sw.js` (served at `/sw.js` with `Service-Worker-Allowed: /`), app icons, `cviky/views/push.py`, template `cviky/install.html`, `static/cviky/push.js`, `tests/test_push.py`
- Modify: `cviky/models.py`, base template

**Interfaces:**
- Produces: `PushSubscription(user FK, endpoint URL unique, p256dh, auth, created_at)`; POST `/push/odebirat/` JSON `{endpoint, keys:{p256dh, auth}}` → 204, upsert by `endpoint` (re-assigns user); settings `VAPID_PUBLIC_KEY`, `VAPID_PRIVATE_KEY`, `VAPID_SUBJECT` from env; `sw.js` handles `push` (show title/body from JSON payload, `data.url`) and `notificationclick` (open/focus `data.url`, default `/`).

- [ ] **Step 1:** Tests: subscribe saves; same endpoint again updates keys, no duplicate; anonymous → 302/403; invalid JSON → 400.
- [ ] **Step 2:** Run → FAIL.
- [ ] **Step 3:** Implement. `/instalace/` page: Czech steps "Sdílet → Přidat na plochu", then a "Zapnout upozornění" button (permission must be asked from a user tap; only shown when `navigator.standalone` or display-mode standalone).
- [ ] **Step 4:** Run → PASS. Manual: Safari on iPhone → add to Home Screen → enable → subscription row appears in admin.
- [ ] **Step 5:** Commit `feat: PWA and push subscription`.

### Task 8: Reminder sender

**Files:**
- Create: `cviky/reminders.py`, `cviky/management/commands/send_reminders.py`, `tests/test_reminders.py`
- Modify: `cviky/models.py`

**Interfaces:**
- Consumes: `todays_series`, `done_today`, `neglected`, `PushSubscription`.
- Produces: `ReminderSent(series FK, date)` unique `(series, date)`;
  ```python
  def due_series(now: datetime) -> list[Series]   # remind_at set, weekday matches local date, remind_at <= local time < remind_at + 60 min, no ReminderSent for today, not all exercises done today
  def reminder_text(series: Series, neglected_count: int) -> tuple[str, str]  # ("Ranní série", "4 cviky + 2 dlouho nedělané"); omit "+ …" when 0
  def send_due(now: datetime) -> int              # sends, records ReminderSent, returns count
  ```
  `send_reminders` command calls `send_due(timezone.now())` once. Push via `pywebpush.webpush(...)`, payload `{"title", "body", "url": "/"}`, TTL 3600. On `WebPushException` with status 404/410 delete that subscription; other errors logged, continue.

- [ ] **Step 1:** Tests (freeze time by passing `now`):
  - `test_due_at_exact_time`, `test_not_due_on_other_weekday`.
  - `test_sent_once_per_day` (two calls → one send).
  - `test_missed_by_30_min_still_sent`, `test_missed_by_90_min_not_sent`.
  - `test_skipped_when_all_done_today`.
  - `test_text_with_and_without_neglected` (Czech plural: 1 cvik, 2–4 cviky, 5+ cviků).
  - `test_gone_subscription_deleted_and_others_still_sent` (mock `webpush` raising 410 for one endpoint).
  - `test_dst_day_sends_once` (2027-03-28 and 2027-10-31, remind_at 07:30).
- [ ] **Step 2:** Run → FAIL.
- [ ] **Step 3:** Implement.
- [ ] **Step 4:** Run → PASS.
- [ ] **Step 5:** Commit `feat: daily reminders`.

### Task 9: Deploy

**Files:**
- Create: `Dockerfile`, `docker-compose.prod.yml` (`web`, `scheduler` = same image running `sh -c 'while true; do python manage.py send_reminders; sleep 60; done'`, `db` postgres with own volume; memory limits), `.github/workflows/deploy.yml`, `README.md` (run, env vars, how to create an invite)
- Modify (on VPS): Vozopis Caddyfile – add `cviky.romanzdk.com` block proxying to `web`; Cloudflare DNS A record `cviky` → VPS IP (DNS only, so Caddy gets the cert)
- Modify: `~/Repos/prehled-projektu/projects.yaml` (new entry with `flow`), then `./deploy.sh` there

**Interfaces:**
- Consumes: everything above. Env on VPS: `SECRET_KEY`, `DATABASE_URL`, `ALLOWED_HOSTS=cviky.romanzdk.com`, `OPENROUTER_API_KEY`, `OPENROUTER_MODEL`, `VAPID_*`.

- [ ] **Step 1:** Copy Vozopis CI/deploy pattern (GHCR image, SSH deploy, `migrate` on deploy, hourly `/healthz` check); add Postgres backup the same way Vozopis does it.
- [ ] **Step 2:** Generate VAPID keys (`vapid --gen` or `py_vapid`), store as secrets; create the OpenRouter key.
- [ ] **Step 3:** Deploy. Verify: `curl -s https://cviky.romanzdk.com/healthz` → `ok`; `curl -s https://muj.vozopis.cz/healthz` still OK.
- [ ] **Step 4:** End-to-end on Roman's iPhone: create invite in admin → register → add to Home Screen → enable notifications → dictate one exercise → create series due in 2 minutes → push arrives → tap opens Today → check off.
- [ ] **Step 5:** Update `projects.yaml`, commit, run `./deploy.sh`. Commit app repo `chore: deploy`.
