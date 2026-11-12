SAMD_QMS is where your organisation records, for each of its software medical devices, problems, complaints, incidents, corrective actions, software changes, controlled documents, training, risks and suppliers. It enforces the quality process: each step asks for the information and the person it needs, approvals are electronically signed, and every change is kept in a permanent audit trail.

## Request an account

If nobody has invited you, request an account from the home page. You need a Google, Microsoft, LinkedIn or ORCID account: there are no SAMD_QMS passwords for new requests.

1. Choose **Request an account**.
2. Tick **I'm not a robot** and wait a moment, then choose **Continue**.
3. Within 15 minutes, choose **Continue with…** and sign in with your provider. This creates your SAMD_QMS account, with no access yet.
4. Fill in who you are, your organisation, the devices or projects you work on, and the role you need, then choose **Send request**.
5. If your provider didn't confirm your email address (ORCID never shares one), we email you a link: open it to confirm.

QA and the teams' Device admins are then emailed. You get an email when your request is approved or declined; once approved, sign in with the same provider. Until then you can only see your request.

## Accept an invitation

Most people join through an invitation email from a Device admin or QA. It lists the devices and your roles on each, and expires after the date shown.

1. Open the link in the email.
2. Choose **Continue with…** and sign in with a Google, Microsoft, LinkedIn or GitHub account that uses the invited email address. Your SAMD_QMS account is created from it; there is no separate username or password to choose. (ORCID can't be used here because it doesn't share your email address; connect it later from **Connected accounts**.)
3. If you already have a SAMD_QMS account with that email address, sign in instead and click **Accept**.

You're then on each device's team with the roles listed. The link works once. If it has expired or says it isn't valid, ask the person who invited you to send it again: each resend replaces the previous link.

The invitation can only be accepted by an account with the email address it was sent to. If you'd rather use another address, ask to be invited at that one.

## Signing in

1. Open the SAMD_QMS address your administrator gave you.
2. Choose **Continue with…** for your provider (Google, Microsoft, LinkedIn, ORCID or GitHub), or enter your username and password.
3. If you see **Access pending**, you're signed in but have no role yet. QA has been emailed; reload the page once they've added you.

Sessions end after 30 minutes without activity.

## Roles

Roles are held **per device**: you can be QA on one device and an Engineer on another. Your roles on each device are shown on its page under **Team** (see [Roles on each device](/help/devices/#roles-on-each-device)).

| Role | Can do on that device |
| --- | --- |
| Engineer | Create and edit records, move them through everyday steps, write documents and submit them for review, add hazards and risk controls, add SOUP items, complete their own training |
| QA | Everything an Engineer can, plus all approvals: closing and rejecting records, approving changes and CAPA plans, approving and releasing documents, accepting risks, approving technical files, setting training requirements; also invites people and manages the team |
| Clinical Safety Officer | Everything an Engineer can, plus complaint reportability decisions and recording reports to the MHRA |
| Device admin | Invites people and manages the device's team and their roles. No approval powers; usually combined with another role |

Things that belong to no device, such as QMS-wide procedures and suppliers, need the role on any of your devices: for example QA on any device can evaluate a supplier.

An administrator can also give someone a role **organisation-wide** in Admin, for example a head of quality who is QA on every device they can see. **All-device access** is not a working role: it lets someone, such as the head of quality or an auditor, see every device and the full audit trail.

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

On the live system, only people whose identity is confirmed by the organisation's sign-in (for example Microsoft or Google with your work email address) can sign. If a signature is refused for that reason, open **Connected accounts** under your name, connect your organisation account, and sign again.

## Electronic signatures

When a step shows a **signature** badge, you confirm it by re-entering your password or signing PIN. Your signature is legally your approval.

Each signature records your name, the date and time, what it means (for example *Approval*, *Risk acceptance*, *Read and understood*) and a fingerprint of exactly what you signed. Signatures can never be edited or removed; they appear in the **Signatures** panel of each record.

Some approvals must be **independent**: you can't approve something you wrote. This applies to closing Problem Reports and Incidents, approving Change Requests and CAPA plans, completing PMS activities, approving document versions and approving technical files. Ask another QA member instead.

## Finding your way

After you sign in you see **Your devices**: the devices whose team you're on and your roles on each. Click **Open** beside one to work in that device's QMS. To switch later, click **Devices** in the top bar and open another; see [Choose a device](/help/devices/#choose-a-device).

The top bar has **Dashboard**, **Records**, **Documents**, **Training**, **Risk**, **Suppliers**, **Devices** and **Audit**. The device menu at the far left also switches device from any page, or choose **All devices**. QA and administrators also see **Admin**, which manages users and roles.

On a phone or narrow window, pages that have a side column (a device, record, document, hazard or supplier) show it below the main content instead of beside it. Wide tables scroll sideways inside their panel.

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
