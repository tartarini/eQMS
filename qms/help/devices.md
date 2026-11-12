Each medical device has its own records, risk file, post-market surveillance (PMS) schedule, SOUP list, software items and technical file. QMS-wide procedures, training, suppliers and roles are shared by every device.

## Choose a device

After you sign in, **Your devices** lists the devices whose team you're on, with your roles on each (a role marked *org-wide* is held organisation-wide and applies on every device). Click **Open** beside a device to work in its QMS: lists, the dashboard and the risk matrices then show only that device, and new records, hazards and documents default to it.

To switch to another device, click **Devices** in the top bar and **Open** another one. The device menu at the left of the top bar does the same from any page. **Work across all my devices** (or **All devices** in the menu) shows everything you can see; every list has a **Device** column so you can always tell them apart.

If you're only a Device admin on a device, you can manage its team but there's no **Open** button: working in its QMS needs the Engineer, QA or Clinical Safety Officer role.

## Your organisation and its roles

Under the EU MDR, the organisation running this QMS is an **economic operator**, and its obligations depend on its role for each device:

- **Manufacturer**: places the device on the market under its own name, and holds its technical file.
- **Authorised representative**: acts in the EU for a manufacturer based outside it. In the UK the equivalent is the UK Responsible Person.
- **Importer**: the first to place a device from outside the EU on the EU market.
- **Distributor**: makes a device available further down the supply chain.

An organisation can hold different roles for different devices, for example manufacturer of one and distributor of another.

**Organisation profile.** Open **Organisation** from the **Your devices** page to see the legal name, registered address, EU Single Registration Number (SRN), MHRA registration number and every role the organisation holds. QA held organisation-wide can change it under **Edit**. A role still set on a device can't be removed from the profile; change those devices first.

**Our role for each device.** QA on a device sets **Our role for this device** under **Edit** on the device page, choosing from the roles in the profile. If you choose **Manufacturer** or **Authorised representative** and leave the matching field below empty, it is filled with the organisation's name and address. The role appears on the device page, on **Your devices**, and in section 1 of the technical file. The completeness check warns while it isn't set.

## Device teams

Each device has a team, shown on its page under **Team**. You can be on as many teams as your work needs, and the device menu lists only your devices.

- You see, and can act on, only the records, risks, device documents and technical files of your teams. QMS-wide documents and your training are visible to everyone.
- Emails and training for a device go only to its team, by role on that device.
- People with **All-device access** (for example the head of quality or an auditor) see every device and the full **Audit** page.
- **Device admins and QA on a team** invite people, add existing users, change roles and remove members. Removing someone keeps their past records and signatures.
- The person who creates a device joins its team as QA and Device admin. A device always keeps at least one member, and at least one Device admin or QA.
- A record's linked hazards must belong to the same device, even if you're on several teams.

## Roles on each device

Everyone on a team has their own roles on that device: Engineer, QA, Clinical Safety Officer and Device admin, in any combination. The same person can hold different roles on another device. See [Roles](/help/getting-started/#roles) for what each one can do.

To change someone's roles (Device admin or QA on the device):

1. Open the device and find them under **Team**.
2. Click **Change**, tick the roles they should hold on this device, and click **Save roles**.

The change takes effect straight away, and training required for their new roles is assigned. You can't change your own roles: ask another Device admin or QA. Roles held organisation-wide are shown under the person's name; only an administrator can change those, in Admin.

To add someone who already has an account, use **Add someone who already has an account** under the team, choose the person and their roles, and click **Add to team**.

## Invite people

Device admins and QA invite new people by email. One invitation can cover several devices, with different roles on each.

1. On a device's page click **Invite people** (or **Invitations → Invite people** in the top bar).
2. Enter the person's email address. Use the address they will sign in with: only an account with this address can accept.
3. Tick their roles on each device. Leave a device blank to leave them off its team. Only devices whose team you manage are listed.
4. Choose when the link expires (14 days by default, at most 30) and, if you like, add a message.
5. Click **Send invitation**.

They get an email with a link. They register with single sign-on (Google, Microsoft, LinkedIn or GitHub) using the invited email address, or sign in if they already have an account, and accept. Invite the address they use with their organisation's sign-in. When they accept, they join each team with the roles you chose. If they already have roles on a device, the invitation adds to them and never removes any.

## Manage invitations

**Invitations** in the top bar lists the invitations you sent, and those for devices whose team you manage.

- **Resend** sends a new link with a fresh expiry. The previous link stops working.
- **Revoke** withdraws an invitation; its link stops working.
- Accepted and revoked invitations stay listed, with who accepted and when.

The person who sent an invitation can resend or revoke it, as can anyone who manages every device in it. If the sender can no longer manage a device's team by the time the invitation is accepted, that device is left out. Every invitation, resend, revocation and acceptance is recorded in the audit trail.

## Add a device

QA only.

1. **Devices → New device**.
2. Enter the name, a short code (for example HRT1) and the regulatory particulars: intended purpose, users and patients, the class for each market (EU MDR, UK MDR 2002 for UKCA, FDA; or *Not for this market*) and the rationale, IEC 62304 software safety class, Basic UDI-DI, manufacturer, markets and standards applied. You can complete these later; they form section 1 of the technical file.
3. List the device's **software items**, one per line (see below).
4. Save. The standard post-market surveillance schedule is set up for the device automatically.

## Software items

Software items are the main parts of a device's software, from its IEC 62304 architecture: for example *Mobile app*, *Image quality check*, *Classification model*, *Clinician portal*. Each device has its own list, edited on the device's **Edit** page.

When a Problem Report, Change Request, hazard or SOUP item asks for a software item, the box suggests the device's items as you type, and only accepts one of them. This keeps trends and the technical file consistent. If a device has no list yet, any name is accepted, and the technical file check warns that the list is missing.

## Put documents in the technical file

When you create or edit a document, set **Device** (leave blank for QMS-wide procedures) and **Technical file section**, for example *2. Information supplied by the manufacturer* for the instructions for use. The effective version of each tagged document is included in that section of the device's technical file.

## Generate and approve a technical file

1. Open the device from **Devices**. The **Technical file** panel shows a completeness check: **errors** must be fixed before approval; **warnings** can be accepted with a reason.
2. Click **Preview** to read the file as it would be generated now.
3. Click **Generate package**. This creates a numbered build (for example TF-HRT1-003): a ZIP containing the technical file in Word and HTML, risk, SOUP and record registers, every effective document file, and a manifest of checksums. Builds can never be changed; generate a new one after fixing gaps.
4. A QA member who didn't generate it opens **Approve**, explains any warnings in the comment, and signs. The previous approved build becomes superseded.

The technical file follows the EU MDR Annex II and III structure: device description, information supplied by the manufacturer, design and manufacturing (including software items, SOUP, release history and known residual anomalies), safety and performance requirements, benefit-risk and risk management, verification and validation, post-market surveillance, and the declaration of conformity. The completeness check confirms the pieces exist, not that they are adequate; QA and your regulatory adviser still review the content.

## Review account requests

People who request an account from the home page appear under **Account requests** in the top bar, with a count of those waiting. Device admins and QA see the list; requests show the person's details, how they signed in and whether their email address is confirmed.

- **Approve onto a device team**: choose a device whose team you manage and their roles on it. They're added to the team, assigned any training their roles need, and emailed. Add them to other teams from those devices' pages.
- **Decline** (QA only): give a reason. It's emailed to them and kept in the audit trail.

A request can't be approved until the person has confirmed their email address. Approved and declined requests can't be changed; every step is in the audit trail.

## My tasks

Each device has a task board for you, under **My tasks** in the menu. It shows what you have to
do on that device, based on the roles you hold there.

- **To do:** actions only your roles can take now: records waiting for your step, documents to
  approve or make effective, technical file builds to approve, training to complete, and approver
  gates you can approve.
- **Waiting on others:** work you started or own that needs another role to act next.
- **Done recently:** electronic signatures you made on this device in the last 30 days.

Each approver gate for the device's documentation route (Greenfield or Retrofit) has its own
column. Gates open in stage order: a stage can be approved only after the stage before it. The
approver role is shown on the card. When it is your turn and you hold that role, enter your
password or signing PIN and choose **Sign and approve this gate**; the approval is an electronic
signature in the audit trail. The next approver is emailed when a gate opens. Nothing else on the board can be dragged or moved by hand: cards change
when the underlying record, document or gate changes.

## People

**People** lists everyone on the teams of the devices you can see, with their roles on each device. It also lists people who hold an organisation-wide role (set by an administrator in Admin); those are read-only here.

Device admins and QA on a device can, for each person on that device's team:

- **Change roles:** tick or untick roles and save. Untick every role to keep someone on the team with no role.
- **Remove from team:** this revokes their access to the device. Their past records and signatures are kept.
- **Add a person:** choose someone with an account who is not yet on the team, then their roles and responsibility.

You can't change your own roles, and a device must keep at least one Device admin or QA on its team. Every change is recorded in the audit trail with who made it and when.

## Acting as one role

If you hold more than one role, the **Acting as** list in the top bar lets you work as one of them. Choose a role and the app works as that role only: what you can do, the functions listed on the dashboard, and the team pages all follow that role. Choose **All my roles** to go back to everything you hold.

The choice can only narrow what you can do. You can't choose a role you don't hold, and the choice is kept for your browser session only.
