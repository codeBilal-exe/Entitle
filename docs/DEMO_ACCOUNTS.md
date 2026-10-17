# Demo accounts

Passwords come from `.env` (see `.env.example`). They are **not** listed on the sign-in page.

On every app start, ENTITLE:

1. Deletes all citizen accounts and their profiles / applications / alerts
2. Recreates staff and admin from the environment
3. Recreates one premade citizen with a filled profile

## Premade citizen

| Field | Value |
|---|---|
| Name | Hina Khan |
| Email | `citizen@entitle.local` |
| Password | `demo-citizen` (or `CITIZEN_PASSWORD` in `.env`) |
| Profile | Age 22, university/college, low income, alerts on |

Startup also installs a few **person-approved** quoted rules so she is **Eligible** for:

- HEC need-based scholarships  
- PEEF scholarships  
- Prime Minister's Youth Programme  

Use those to show **Prepare an application** → review packet (not sent yet).

## Staff / admin

| Role | Email | Password (default in `.env`) |
|---|---|---|
| Admin | `admin@entitle.local` | `demo-admin` |
| Staff | `staff.one@entitle.local` | `demo-staff` |
| Staff (spare) | `staff.two@entitle.local` | `demo-staff-2` |

- **Staff** — review drafts (Rule changes), release or hold bad news (Reviews)
- **Admin** — same as staff, plus edit source URLs, toggle sending, open Activity

## Env keys

```
ADMIN_EMAIL / ADMIN_PASSWORD
STAFF_ONE_EMAIL / STAFF_ONE_PASSWORD
STAFF_TWO_EMAIL / STAFF_TWO_PASSWORD
CITIZEN_EMAIL / CITIZEN_PASSWORD / CITIZEN_DISPLAY_NAME
```
