# Bureau User Guide

This guide is for Tigrai Culture and Tourism Bureau staff using the console at `/en/bureau` (also available in `/ti/bureau` and
`/am/bureau`).

## Signing in

1. Sign in with your work email and password, or with single sign-on if your administrator enabled it.
2. **Second factor:** the first time, scan the setup code with an authenticator app (any TOTP app), or type the secret it shows,
   then enter the 6-digit code. After that, enter a fresh code each time you sign in. Without this step your staff tools stay locked.
3. Sessions end after 8 hours. Always sign out on shared computers.

## What you can do depends on your role

| Role | Main tasks |
|---|---|
| Content editor | Create and edit destinations, categories, events, media; publish |
| Heritage specialist | Review heritage text, publish, manage restricted knowledge |
| Translator / reviewer | Translate (`ti`, `am`); a *different* reviewer approves |
| Geographic officer | Set coordinates and how precisely the public sees them; record verified route segments |
| Tourism officer | Advisories, events, measured visitor statistics, assistant |
| Moderator | Review stories, comments, reports and appeals |
| Provider verifier | Check licences and verify providers |
| Competition admin / approver / finance / judge | Run awards with separate approvals |
| Knowledge curator | Upload and review documents for the AI guide |
| Executive / auditor | Dashboards, exports, audit log |
| System administrator | Staff accounts, roles, feature flags, AI policy |

## Everyday workflows

### Update a destination
1. **Destinations → choose a place → Content tab.** Edit the English text. Other languages are under their own tabs.
2. **Details:** visit duration, accessibility, permits and contacts. Leave a field **unknown** if you have not verified it. The public
   site will then say "unknown" instead of guessing.
3. **Sources:** add the documents you relied on. **Mark verified** records today's date.
4. **Publish** (or schedule). The public page changes only when you publish. Your drafts are never public.
5. Made a mistake? **Revisions → compare → roll back.**

### Protect a sensitive site
On **Geo**, choose *Approximate* (the public sees roughly 10 km precision) or *Hidden*. Only staff with heritage permission see exact
coordinates.

### Emergency takedown
**Archive** removes a destination from public view immediately. For safety, publish an **advisory**. If an advisory says *travel not
advised* for the whole region, the trip planner stops producing travel routes and offers virtual exploration.

### Add knowledge for the AI guide
**Knowledge Vault → Upload.** Fill in author, publisher, date, language, rights and classification. A **different** colleague reviews
and approves. The system then checks the guide can find the document, and you **Publish** it. Use **Withdraw** to remove it from the
guide instantly. Sacred or restricted material needs the custodian's approval reference.

### Moderate stories
**Moderation queue:** read the story and check any flags (contact details, coordinates, spam words). Flags are hints only; **you**
decide. Approve or reject with a short note; the author is informed. Appeals must be decided by a *different* moderator.

### Journals and Spaces
Journal stories appear in the **Moderation queue** like visitor stories. Approving one publishes it and notifies its subscribers
once. Space messages are live, but messages with warning signs are **held**: only the author and moderators see them until you
approve or remove them. For a heated channel, turn on **slow mode**. To pause a person, set a time-limited **restriction**; they
cannot get around it by leaving and rejoining the space.

### Run a competition (when authorized)
The competition cannot open until legal terms, funding and Bureau authorization are each recorded **by a different person**, and an
administrator turns on live competitions with a written justification. Judges declare conflicts before scoring, and winners need a
second approver.

### Reports
**Analytics:** choose dates, then export CSV, Excel or PDF. Every report states when it was made, its filters, and that *website
engagement is not visitor arrivals*. Enter real visitor counts under **Measured tourism** with their source.

### Ask the assistant
Ask in plain language, for example "Which destinations have outdated information?" or "Summarize activity this month". It answers
only with data your role can see, and its output is always a **draft**. It cannot publish, approve or change anything.

## Getting help
Contact your system administrator. Report suspected security problems immediately (see `SECURITY.md`).
