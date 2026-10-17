# Design

ENTITLE is a person and a model working together. The model may draft and explain. A person decides. Say that in plain words on the sign-in page, the home page, and every approval step.

## One job per screen

Short sentences. Everyday words.

Citizen: Sign up → fill in your profile → see what matches → prepare an application → approve the packet → alerts.

Staff: Sign in → see sources and drafts waiting → approve a change only if the quotes match → release or hold bad news.

Admin: Sign in → the staff work, plus sources and the sending switch. The activity log is there too.

## Three human stops, visible in the product

1. **Rule change.** Staff open a draft. The quote check is shown. Approve and Reject are the actions. The model does not approve.
2. **Bad news.** Staff see a name and the eligibility change, not the private profile. Release or Hold are the actions.
3. **Packet.** The applicant sees the exact details and approves them before anything is sent.

These three stops are listed on sign-in and home, and the current stop is marked on the screen where the person acts.

## Sign-in

An empty email field, an empty password field, and a Sign in button. Sign up is on the same page. No filled-in passwords. No "sign in as this person" buttons.

## Roles

Citizen, staff, and admin are stored on the account. There is no Citizen view / Staff view switch. Navigation follows the role. The server refuses a page the role cannot open.

## Catalogue

Programme names and official URLs. A quote appears only when it was on a page ENTITLE fetched. If the page cannot be read, the screen says the source is unreachable. Do not label the list as a demo sample.

## Alerts

Useful sentences, not status codes. Programme, what changed, what it means, the quote, whether a person released it, the date, and one next step. Separate "you may now qualify" from "you may no longer qualify". Unread count in the navigation. Opening an alert marks it read. The empty state says alerts appear when a watched notice changes the result.

## What the model does not do

It does not decide eligibility. It does not send a packet. It does not release bad news. Those stay with the rule engine, the quote check, the approval gate, and a person.
