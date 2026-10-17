# ENTITLE product

This is the product to build and show. Citizens sign up themselves. Rules come from official pages a person approves.

## What it is

ENTITLE watches public programme notices. Code re-checks who is affected when a notice changes. A person approves a rule change. A person releases bad news. The applicant approves the exact packet. The model may draft and explain. It does not decide eligibility and it does not send on its own.

Say that in plain words on the sign-in page, the home page, and every approval step. The three human stops are screens with actions, not only a paragraph.

## Accounts

- Sign-in is an empty email and password form, with Sign up on the same page.
- A new citizen has no profile until they save one.
- One admin and two staff accounts are created from environment variables. They are not listed on the sign-in page.
- Roles are `citizen`, `staff`, and `admin`. There is no view toggle.

## Access

Enforce on the server. A second citizen gets 403 when they request the first citizen's profile, application, or alerts. Staff and admin get 403 on a private profile. Citizens get 403 on staff and admin tools. Staff cannot turn sending off and cannot create accounts.

## Catalogue

At least ten real official programmes, each with its official URL. No synthetic quota. No "demo sample" label. Quotes only from text ENTITLE fetched. Unreachable pages say so.

## Alerts

Programme name, what changed, one sentence on what it means, the quote, whether a person released it, the date, and one next step. Separate gains from losses. Unread count in the navigation. Mark read on open. Empty state explains when alerts appear.

## What stays

The rule engine, the quote check, and the approval gate. The timer and Check sources now. Deadline reminders. Local SQLite. The app runs if n8n is down.

## Done when

- Sign-in and sign-up are empty forms.
- A new citizen has no profile until they create one, and another user cannot open it.
- One admin and two staff accounts exist and are not listed on the sign-in page.
- The catalogue is real official programmes and real quotes only.
- Alerts explain the change and the next step, with an unread count.
- Every important step shows that a person, not the model, approves it.
- Docs and tests match the app.
