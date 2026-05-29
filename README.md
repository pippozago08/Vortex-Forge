# Vortex Forge Platform

Piattaforma Django full-stack per un sito professionale di vendita PC su misura con:

- autenticazione sicura con validazione password lato server;
- reset password reale tramite email configurabile;
- ruoli `super admin`, `admin autorizzato`, `utente`;
- sistema ban temporaneo o permanente con revoca;
- catalogo build persistente con immagini multiple, disponibilita, badge commerciali e visibilita controllata;
- richieste build personalizzate e richieste commerciali sulle build;
- richieste build personalizzate con budget minimo/massimo, approvazione admin, prezzo finale e pagamento simulato;
- modulo contatti salvato in database;
- pannello admin custom protetto con dashboard, gestione build, utenti, ban, richieste e impostazioni;
- struttura pagamenti pronta per futuro PayPal Business tramite variabili ambiente;
- pagine legali, footer professionale, dark/light mode persistente;
- interfaccia pubblica e backoffice bilingui con selettore lingua `IT / EN`;
- progetto organizzato per deploy reale.

## Stack

- Backend: Django 5
- Database locale: SQLite
- Database produzione: pronto per PostgreSQL tramite variabili ambiente
- Upload immagini: Django media files
- Email: backend SMTP configurabile via `.env`
- Pagamenti: modalita `simulated` pronta per futuro provider PayPal Business

## Struttura principale

- `vortexforge/`: configurazione progetto
- `accounts/`: utenti, ruoli, ban, reset password, login
- `catalog/`: build, galleria immagini, richieste custom e richieste build
- `contacts/`: modulo contatti
- `core/`: home, pagine legali, impostazioni sito, log admin
- `backoffice/`: pannello amministrativo custom
- `templates/`: tutte le pagine frontend e admin
- `static/`: CSS e JS globali
- `locale/`: file traduzione Django
- `scripts/compile_translations.py`: compilazione `.po -> .mo` senza dipendenze GNU gettext

## Avvio locale

1. Crea e attiva un ambiente virtuale Python.
2. Installa le dipendenze:

```powershell
python -m pip install -r requirements.txt
```

3. Crea il file `.env` partendo da `.env.example`.
4. Applica le migrazioni:

```powershell
python manage.py migrate
```

5. Crea il super admin iniziale:

```powershell
python manage.py bootstrap_super_admin --email owner@example.com --username owner --password "CambiaQuesta!2026" --first-name Owner --last-name Admin
```

6. Avvia il server:

```powershell
python manage.py runserver
```

## Multilingua

- lingua di default: italiano
- lingua aggiuntiva: inglese
- cambio lingua dal selettore in header
- preferenza salvata tramite sessione/cookie Django

I contenuti dinamici principali hanno anche campi inglesi nel backoffice:

- build: nome, descrizioni, componenti, categoria
- impostazioni sito: hero e messaggio fiducia

Se modifichi il file traduzioni `locale/en/LC_MESSAGES/django.po`, ricompila con:

```powershell
python scripts/compile_translations.py
```

## Credenziali admin locali gia create

Nel database locale corrente e gia stato creato un super admin di sviluppo:

- email: `owner@vortexforge.local`
- username: `owner`
- password: `VortexForge!Admin2026`

Cambia subito queste credenziali o ricrea il database prima della pubblicazione online.

## URL principali

- sito pubblico: `http://127.0.0.1:8000/`
- area account: `http://127.0.0.1:8000/account/`
- richiesta custom: `http://127.0.0.1:8000/builds/custom/`
- pannello admin custom: `http://127.0.0.1:8000/admin-panel/`
- admin Django tecnico: `http://127.0.0.1:8000/django-admin/`

## Configurazione email

Per rendere funzionante il reset password via email, imposta nel file `.env`:

- `SITE_PUBLIC_URL`
- `SITE_SUPPORT_EMAIL`
- `EMAIL_BACKEND=django.core.mail.backends.smtp.EmailBackend`
- `EMAIL_HOST`
- `EMAIL_PORT`
- `EMAIL_HOST_USER`
- `EMAIL_HOST_PASSWORD`
- `EMAIL_USE_TLS`
- `DEFAULT_FROM_EMAIL`

In sviluppo puoi usare temporaneamente il backend console lasciando `DJANGO_DEBUG=True`.

### Cos'e SMTP

SMTP e il sistema usato dai server email per inviare messaggi. Nel progetto serve per:

- recupero password;
- notifiche di richiesta approvata;
- notifiche di pagamento demo confermato;
- messaggi tecnici del sito.

Per Gmail non basta la password normale dell'account: quando creerai `vortexforge.support@gmail.com`, dovrai attivare la verifica in due passaggi e generare una password per app. Quella password andra in `EMAIL_HOST_PASSWORD`, non nel codice.

Esempio Gmail futuro:

```env
EMAIL_BACKEND=django.core.mail.backends.smtp.EmailBackend
EMAIL_HOST=smtp.gmail.com
EMAIL_PORT=587
EMAIL_HOST_USER=vortexforge.support@gmail.com
EMAIL_HOST_PASSWORD=password-per-app-google
EMAIL_USE_TLS=True
DEFAULT_FROM_EMAIL=Vortex Forge <vortexforge.support@gmail.com>
```

Finche non hai la mail reale, puoi lasciare:

```env
EMAIL_BACKEND=django.core.mail.backends.console.EmailBackend
```

In questo modo le email vengono stampate nel terminale e il progetto resta testabile.

## Configurazione pagamenti

Il progetto non attiva ancora pagamenti live, ma e gia predisposto per un checkout serio.

Variabili ambiente principali:

- `PAYMENT_PROVIDER=simulated`
- `PAYMENT_DEFAULT_CURRENCY=EUR`
- `SIMULATED_PAYMENTS_ENABLED=True`
- `PAYPAL_CLIENT_ID=...`
- `PAYPAL_CLIENT_SECRET=...`
- `PAYPAL_ENVIRONMENT=sandbox`
- `PAYPAL_WEBHOOK_ID=...`
- `PAYPAL_BRAND_NAME=Vortex Forge`

Stato attuale:

- `simulated`: checkout dev completo a step senza denaro reale
- `paypal`: struttura pronta ma integrazione API Orders/Capture non ancora attivata

Checkout dev attuale:

1. il cliente apre la pagina checkout della richiesta approvata
2. controlla riepilogo, prezzo finale e riferimenti della richiesta
3. sceglie un metodo di pagamento visuale tra `PayPal`, `Mastercard`, `Visa`, `American Express`
4. avvia il checkout con creazione del tentativo pagamento e dell`order id`
5. completa la conferma pagamento simulata
6. il sistema registra esito riuscito o fallito con storico, provider, metodo scelto, importo, order id e transaction id

Punti del progetto gia pronti per PayPal Checkout reale:

- `payments/gateways.py`: punto di innesto provider e metodi `create_order`, `capture_order`, `verify_webhook`
- `payments/service.py`: orchestrazione checkout, stato richiesta e storico tentativi
- `catalog/models.py`: modello `CustomBuildPayment` con provider, order id, transaction id e stato
- `templates/catalog/custom_request_payment.html`: pagina pagamento lato cliente
- `templates/backoffice/requests.html`: vista admin di approvazione / approvate / pagate
- `templates/backoffice/custom_request_review.html`: riepilogo admin della richiesta con dettagli checkout

Agganci futuri PayPal Business:

- `payments/gateways.py -> PayPalGateway.create_order()`: creazione ordine PayPal Orders API
- `payments/gateways.py -> PayPalGateway.capture_order()`: capture del pagamento dopo approvazione cliente
- `payments/gateways.py -> PayPalGateway.verify_webhook()`: verifica webhook PayPal
- `payments/service.py`: punto centrale per cambiare stato richiesta, salvare order id e transaction id

Flusso attuale:

1. utente invia richiesta custom con componenti e budget
2. admin/super admin approvano e impostano il prezzo finale
3. solo dopo approvazione compare il pulsante pagamento
4. in ambiente dev il checkout e simulato con esito riuscito/fallito
5. al successo la richiesta passa a `Pagata`

## Modalita progetto scolastico/test

Per ora il progetto e configurato per essere presentato come piattaforma completa ma non come ecommerce live:

- `PAYMENT_PROVIDER=simulated`
- nessun IBAN o dato bancario nel codice
- nessuna chiave PayPal reale
- nessuna Partita IVA obbligatoria
- checkout demo con storico, stato e riferimenti simulati
- email stampate nel terminale finche SMTP non viene configurato

Questa modalita e adatta alla presentazione scolastica perche mostra il flusso completo senza trattare soldi reali o dati sensibili.

## Preparazione dominio reale

Il progetto e gia predisposto per passare senza refactor da ambiente locale a dominio reale.

Quando acquisterai il dominio:

1. imposta nel file `.env`:
   - `SITE_PUBLIC_URL=https://www.tuodominio.it`
   - `SITE_SUPPORT_EMAIL=support@tuodominio.it`
   - `DJANGO_ALLOWED_HOSTS=tuodominio.it,www.tuodominio.it`
   - `DJANGO_CSRF_TRUSTED_ORIGINS=https://tuodominio.it,https://www.tuodominio.it`
2. configura SMTP con la casella reale del dominio oppure con Google Workspace/Gmail
3. aggiorna dal pannello admin `Impostazioni sito` l'email pubblica di supporto, se necessario

Dettagli importanti:

- le email di reset password usano il mittente configurato in `DEFAULT_FROM_EMAIL`
- i link email usano `SITE_PUBLIC_URL` quando il progetto gira ancora in locale
- il sito sostituisce automaticamente il vecchio placeholder `support@vortexforge.local` con il valore di `SITE_SUPPORT_EMAIL`

## Configurazione database

### Sviluppo locale

Usa SQLite:

- `DB_ENGINE=django.db.backends.sqlite3`
- `DB_NAME=db.sqlite3`

### Produzione con PostgreSQL

Imposta per esempio:

- `DB_ENGINE=django.db.backends.postgresql`
- `DB_NAME=vortexforge`
- `DB_USER=vortexforge_user`
- `DB_PASSWORD=...`
- `DB_HOST=...`
- `DB_PORT=5432`

## Deploy consigliato

### Render

Sono stati aggiunti file pronti per Render:

- `render.yaml`: blueprint con web service Python e database PostgreSQL;
- `build.sh`: installazione dipendenze, `collectstatic` e migrazioni;
- `runtime.txt`: versione Python consigliata;
- `requirements.txt`: include `gunicorn`, `whitenoise`, `psycopg` e `dj-database-url`.

Passaggi consigliati:

1. Carica il progetto su GitHub.
2. Su Render crea un nuovo Blueprint oppure un Web Service collegato al repository.
3. Se usi il Blueprint, Render legge `render.yaml`.
4. Dopo il primo deploy, aggiorna `SITE_PUBLIC_URL` con l'URL reale assegnato da Render.
5. Quando comprerai un dominio, collegalo a Render e aggiorna:
   - `DJANGO_ALLOWED_HOSTS`
   - `DJANGO_CSRF_TRUSTED_ORIGINS`
   - `SITE_PUBLIC_URL`

In produzione il sito usa WhiteNoise per gli static files e `DATABASE_URL` per PostgreSQL.

### VPS o server Linux

1. Installa Python 3.12+.
2. Clona il progetto.
3. Configura `.env` di produzione con:
   - `DJANGO_DEBUG=False`
   - `DJANGO_ALLOWED_HOSTS=tuodominio.it,www.tuodominio.it`
   - `SESSION_COOKIE_SECURE=True`
   - `CSRF_COOKIE_SECURE=True`
   - `SECURE_SSL_REDIRECT=True`
   - `SECURE_HSTS_SECONDS=31536000`
4. Installa dipendenze:

```bash
python -m pip install -r requirements.txt
```

5. Esegui:

```bash
python manage.py migrate
python manage.py collectstatic --noinput
python manage.py bootstrap_super_admin --email admin@tuodominio.it --username admin --password "UnaPasswordMoltoForte!2026"
gunicorn vortexforge.wsgi:application --bind 0.0.0.0:8000
```

6. Metti Nginx o un reverse proxy davanti a Gunicorn.
7. Configura HTTPS con certificato SSL.
8. Usa PostgreSQL in produzione.
9. Salva `media/` su volume persistente o storage esterno.

### Deploy container

E presente anche un `Dockerfile` e un `Procfile` come base iniziale per hosting containerizzati o PaaS.

## Note operative importanti

- Le build non sono hardcoded nel frontend: vanno gestite dal pannello admin.
- Le password sono hashate con il sistema nativo Django.
- I ban vengono controllati sia al login sia durante la navigazione di un utente gia autenticato.
- Il reset password usa token e codice di verifica con scadenza registrati nel database.
- Le richieste custom hanno stati separati per approvazione e pagamento: `in_approval`, `approved`, `payment_pending`, `paid`, `payment_failed`, `rejected`, `cancelled`.
- Gli importi approvati e i tentativi di pagamento vengono salvati a database nel modello `CustomBuildPayment`.
- Gli admin non devono mai condividere le credenziali create per sviluppo.
