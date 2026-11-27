# Fyzio cviky – návrh (v1)

Pracovní název: **fyzio-cviky**. Datum: 2026-11-27.
Značení: **(R)** = rozhodl Roman, **(C)** = návrh Clauda, Roman ho zatím výslovně nepotvrdil.

## Proč

Na fyzioterapii dostaneš pokaždé několik cviků. Když nějaký cvik chvíli neděláš nebo máš pauzu, zapomeneš, **že vůbec existuje**, a přestaneš ho dělat (R). Zahraniční appky (Physitrack, Wibbi, MedBridge) jsou obrovské, složité a nejsou česky (R).

Úspěch: cviky od fyzioterapeuta nevypadnou z cvičení. Appka sama připomíná, co máš dnes cvičit a co jsi dlouho nedělal.

## Cíle (v1)

1. Česká webová appka na mobil (iPhone), přidaná na plochu (PWA) (R).
2. **Nadiktování cviku**: po fyzioterapii nadiktuješ cvik vlastními slovy, LLM z toho udělá kartu cviku (R).
3. **Karta cviku**: název, oblast těla, poloha, štítky, kroky, na co dát pozor, počet opakování / délka a tvůj původní text (R+C).
4. **Série**: cviky poskládáš do sérií (např. ranní, večerní) (R).
5. **Obrazovka „Dnes“**: co máš dnes cvičit + sekce „Dlouho jsi nedělal“. Každý cvik se odklikává zvlášť (C, odsouhlaseno).
6. **Upozornění** na telefon v nastavený čas (R).
7. **Fulltextové hledání** („krk“, „pater“ najde „páteř“) a filtry podle oblasti a polohy (R).
8. Více uživatelů, každý vidí jen svoje cviky. Registrace **jen na pozvání** (R).

## Mimo v1 (nápady na později)

- Veřejný sdílený katalog cviků a zveřejňování vlastních cviků ostatním.
- Účty pro fyzioterapeuty, kteří zadávají cviky klientům, a placení.
- Generované AI obrázky (riziko špatné polohy těla).
- Video ke cviku (C: dobrý nápad na v2, natočit fyzioterapeuta, jak cvik předvádí).
- Nativní iOS appka, Android.
- Otevřená registrace pro kohokoli.

## Čemu se vyhnout (anti-cíle)

- Složitost jako u zahraničních appek. Přidání cviku musí jít za chvilku po návratu z fyzioterapie.
- Appka ukazuje špatně provedený cvik (proto žádné AI obrázky v1).
- Upozornění nechodí (to je hlavní funkce).

## Omezení

- iPhone: Web Push funguje jen pro appku přidanou na plochu (iOS 16.4+). Upozornění musí posílat server.
- Klíč k LLM jen na serveru.
- Hosting zdarma = stejný Hetzner VPS jako Vozopis (R). Vlastní Docker kontejner a vlastní databáze, nová doména přes Caddy. Nesmí ohrozit běh Vozopisu.
- Popisy cviků jsou zdravotní informace: posílat jen do LLM bez trénování na datech (C: OpenRouter účet se zapnutým ZDR, který už máš ověřený).

## Možnosti, které jsme zvažovali

| Možnost | Výhody | Nevýhody | Výsledek |
|---|---|---|---|
| **A) Django + Postgres na vlastním VPS** | stejný stack jako Vozopis, přihlášení a admin hotové, 0 Kč navíc | Web Push napsat sám | **vybráno (R)** |
| B) Supabase / Firebase | přihlášení hotové | push a LLM stejně potřebují vlastní funkci, další služba | zamítnuto |
| C) Nativní iOS appka | spolehlivá upozornění | App Store / 99 USD ročně, jen iOS | zamítnuto |
| Free hostingy (Render, Railway) | zdarma | server usíná, upozornění by nechodila | zamítnuto |
| Cloudflare Workers + D1 | zdarma | jiný jazyk, vše znovu | zamítnuto |

## Jak to funguje

### Stack (R, podle Vozopisu)
Django, Postgres, Caddy, Docker, nasazení přes GitHub Actions + SSH na Hetzner VPS, image v GHCR. Healthcheck `/healthz` jako u Vozopisu. Šablony v Djangu, minimum JS (service worker pro push a PWA manifest) (C).

### Přidání cviku (R, detaily C)
0. Jeden diktát = jeden cvik (R). Po uložení tlačítko „Přidat další cvik“.
1. Tlačítko „Nadiktovat nový cvik“ otevře textové pole.
2. Diktuje se mikrofonem v klávesnici iPhonu (česky, bez vlastního kódu pro rozpoznání řeči) (C).
3. Po odeslání server pošle text do LLM. LLM vrátí JSON: `nazev`, `oblast` (z pevného seznamu), `poloha` (z pevného seznamu), `stitky` (vč. podobných slov, např. krk → krční páteř, šíje), `kroky`, `pozor_na`, `opakovani` (volitelně) (C).
4. Uživatel vidí předvyplněnou kartu, může cokoli upravit (oblast a polohu výběrem z menu) a uloží. Původní text se ukládá vždy (C).
5. Když LLM selže, karta se uloží jen s původním textem a polem k ručnímu vyplnění (C).

Pevné seznamy (C, builder může doladit):
- Oblast: krk, ramena, hrudní páteř, bederní páteř, pánev/kyčle, kolena, kotníky/chodidla, zápěstí/ruce, celé tělo.
- Poloha: sed, stoj, leh na zádech, leh na břiše, leh na boku, na čtyřech.

### Ilustrace (C)
Bez AI obrázků. Karta ukazuje obrys těla se zvýrazněnou oblastí + ikonku polohy (cca 15 jednoduchých SVG).

### Série a „Dnes“ (C, odsouhlaseno)
- Série = pojmenovaný seznam cviků + dny v týdnu + čas upozornění.
- „Dnes“ = série naplánované na dnešek s jejich cviky a stav odkliknutí.
- „Dlouho jsi nedělal“ = cviky z kterékoli série, které nebyly odkliknuty X dní (výchozí 7, nastavitelné v profilu). Cvik, který nikdy nebyl odkliknut, se počítá od přidání do série.
- Odkliknutí = záznam (cvik, datum a čas). Jeden cvik jde odkliknout víckrát za den (např. ráno i večer), „Dnes“ ukazuje stav pro danou sérii.

### Upozornění (R, detaily C)
- Web Push (VAPID). Povolení se žádá až po přidání na plochu, s krátkým návodem „Přidat na plochu“.
- Každá série pošle upozornění ve svůj čas ve své dny: „Ranní série – 4 cviky“. Když jsou dlouho nedělané cviky, připíše se „+ 2 dlouho nedělané“. Klepnutí otevře „Dnes“.
- Když je série dnes už celá odkliknutá, upozornění se nepošle (C).
- Plánovač: úloha spouštěná každou minutu (cron / management command v kontejneru), časové pásmo Europe/Prague.

### Hledání (R, detaily C)
Postgres fulltext s `unaccent` přes název, štítky, kroky a původní text. Filtry: oblast, poloha, série.

### Účty (R: jen na pozvání)
Django auth. Pozvánku vytvoříš v Django adminu (jednorázový odkaz pro registraci) (C). Každý uživatel vidí jen svoje cviky a série.

## Necháno na builderovi
- Repo `romanzdk/fyzio-cviky`, soukromé (C).
- Konkrétní LLM model na OpenRouteru (levný, dobře česky, umí JSON výstup).
- Doména: `cviky.romanzdk.com` – subdoména tvé domény, DNS v Cloudflare, zdarma (C, Roman chtěl „cokoliv zdarma“).
- Přesný vzhled, SVG ikonky, struktura projektu.
- Zápis do `~/Repos/prehled-projektu/projects.yaml` po nasazení.
