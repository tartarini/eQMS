SAMD_QMS is where your organisation records, for each of its software medical devices, problems, complaints, incidents, corrective actions, software changes, controlled documents, training, risks and suppliers. It enforces the quality process: each step asks for the information and the person it needs, approvals are electronically signed, and every change is kept in a permanent audit trail.

## Signing in

1. Open the SAMD_QMS address your administrator gave you.
2. Choose **Continue with…** for your provider (Google, Microsoft, LinkedIn, ORCID or GitHub), or enter your username and password.
3. If you see **Access pending**, you're signed in but have no role yet. QA has been emailed; reload the page once they've added you.

Sessions end after 30 minutes without activity.

## Roles

Your role says what you can do; your device teams say which devices you can do it on (see [Device teams](/help/devices/#device-teams)).

| Role | Can do |
| --- | --- |
| Engineer | Create and edit records, move them through everyday steps, write documents and submit them for review, add hazards and risk controls, add suppliers and SOUP items, complete their own training |
| QA | Everything an Engineer can, plus all approvals: closing and rejecting records, approving changes and CAPA plans, approving and releasing documents, accepting risks, evaluating suppliers, setting training requirements, managing device teams |
| Clinical Safety Officer | Everything an Engineer can, plus complaint reportability decisions and recording reports to the MHRA |

**All-device access** is not a working role: it lets someone, such as the head of quality or an auditor, see every device and the full audit trail.

## Connected accounts

Under your name in the top bar, **Connected accounts** links sign-in accounts you hold elsewhere (Google, Microsoft, LinkedIn, ORCID, GitHub) to your SAMD_QMS account, so you can sign in with them. Connecting an account gives no extra access.

- Click **Connect** next to a provider, sign in there, and you're brought back.
- To stop using one, select it and click **Remove selected**.
- ORCID doesn't share your email address, so it can't be your first sign-in: sign in another way, then connect your ORCID iD here.
- If the page says no sign-in providers are switched on, your administrator hasn't enabled single sign-on yet.

## Signing PIN

If you sign in with single sign-on you have no SAMD_QMS password, so you need a signing PIN before you can approve anything.

1. Sign out and sign in again.
2. Within 15 minutes, open **Signing PIN** under your name in the top bar.
3. Enter a PIN of at least 6 characters twice and save.

Local-account users can set a PIN too. Once set, the PIN replaces your password whenever you sign.

## Electronic signatures

When a step shows a **signature** badge, you confirm it by re-entering your password or signing PIN. Your signature is legally your approval.

Each signature records your name, the date and time, what it means (for example *Approval*, *Risk acceptance*, *Read and understood*) and a fingerprint of exactly what you signed. Signatures can never be edited or removed; they appear in the **Signatures** panel of each record.

Some approvals must be **independent**: you can't approve something you wrote. This applies to closing Problem Reports and Incidents, approving Change Requests and CAPA plans, completing PMS activities, approving document versions and approving technical files. Ask another QA member instead.

## Finding your way

The top bar has **Dashboard**, **Records**, **Documents**, **Training**, **Risk**, **Suppliers**, **Devices** and **Audit**. Use the device menu at the far left to focus every page on one device, or choose **All devices**. QA and administrators also see **Admin**, which manages users and roles.

Help is always one click away:

- **Help** at the top right of every page opens the part of this guide about that page, in a new tab.
- The **?** beside a form field explains what to enter. Click it to open the explanation, and **More in the guide** for the full field reference.

## The dashboard

The **Dashboard** shows open records by type, upcoming and overdue deadlines, open items with patient-safety impact, your training, documents in review or due for review, unacceptable risks, supplier evaluations due, and anything assigned to you. Use **+ New** under a record type to create a record.

## Emails you'll get

| Email | Sent to |
| --- | --- |
| New incident (marked URGENT) | QA and Clinical Safety Officers on the device's team, immediately |
| New complaint | QA on the device's team |
| A record is assigned to you | The new owner |
| A record reaches a step that needs a particular role | People in that role on the device's team, and the owner |
| A document is submitted for review | QA |
| Training assigned | Each person who needs it |
| New single sign-on user waiting for a role | QA and administrators |
| Daily digest of overdue and due-soon items (next 7 days) | Each person with items, and QA |
