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
- A **QMS admin** (set by an administrator in Admin) manages the application overall: they see every device and can manage every device's team, without being on it. A QMS admin holds no working role and signs nothing.
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

## Follow the documentation route

The **Documentation route** panel at the top of a device's page shows how far its documentation has got. It follows the route set on the device record (**Documentation route** on the edit form):

- **Greenfield**, documentation from the start of development: six stages, 1 to 6.
- **Retrofit**, an existing device whose documentation is reconstructed: seven steps, A to G.

Each check is worked out from what the QMS already holds, so it updates as you work; nothing is ticked by hand. Click an open check to go where it is fixed. The stage you are on opens by itself.

### The diagram

The top of the panel is a diagram of the route: one circle per stage, joined by a line, with the count of checks passed under each (for example 4/5). A circle is grey when nothing has started, amber when in progress and green when done; the stage you are on, the first one not finished, has a blue ring. Click a stage to open its checks below. On a phone or narrow window the diagram runs top to bottom.

A diamond before a stage is that stage's **approver gate**, signed on **My tasks**:

- **Green**: the gate is approved.
- **Amber**: its gate checks pass and it is awaiting sign-off.
- **Red outline**: its gate checks are not passing yet, so it can't be signed.
- **Dashed amber outline**: the gate was approved, but its gate checks no longer pass, for example because a document was withdrawn. Look at what changed.

Greenfield has gates before stages 2, 4, 5 and 6. Retrofit has a gate on every step, A to G.

### Route at a glance

These are the two routes as the diagram draws them. A diamond marks a stage with an approver gate. The examples show a device with nothing done yet.

<div class="route-example">
<svg viewBox="0 0 720 170" role="img" aria-label="Greenfield route: stages 1 to 6" style="width:100%;max-width:720px;height:auto;font-family:inherit">
<title>Greenfield route: stages 1 to 6</title>
<line x1="60" y1="92" x2="660" y2="92" stroke="#9a9a94" stroke-width="2"/>
<circle cx="60" cy="92" r="17" fill="#ecebe6" stroke="#9a9a94" stroke-width="2"/>
<text x="60" y="97" text-anchor="middle" font-size="14" font-weight="700" fill="#5a5a55">1</text>
<text x="60" y="132" text-anchor="middle" font-size="13" font-weight="600" fill="currentColor">Set-up</text>
<circle cx="180" cy="92" r="17" fill="#ecebe6" stroke="#9a9a94" stroke-width="2"/>
<text x="180" y="97" text-anchor="middle" font-size="14" font-weight="700" fill="#5a5a55">2</text>
<rect x="173" y="39" width="14" height="14" transform="rotate(45 180 46)" fill="#fff" stroke="#b3261e" stroke-width="2"/>
<text x="180" y="132" text-anchor="middle" font-size="13" font-weight="600" fill="currentColor">Purpose and</text>
<text x="180" y="147" text-anchor="middle" font-size="13" font-weight="600" fill="currentColor">classification</text>
<circle cx="300" cy="92" r="17" fill="#ecebe6" stroke="#9a9a94" stroke-width="2"/>
<text x="300" y="97" text-anchor="middle" font-size="14" font-weight="700" fill="#5a5a55">3</text>
<text x="300" y="132" text-anchor="middle" font-size="13" font-weight="600" fill="currentColor">Requirements</text>
<text x="300" y="147" text-anchor="middle" font-size="13" font-weight="600" fill="currentColor">and design</text>
<circle cx="420" cy="92" r="17" fill="#ecebe6" stroke="#9a9a94" stroke-width="2"/>
<text x="420" y="97" text-anchor="middle" font-size="14" font-weight="700" fill="#5a5a55">4</text>
<rect x="413" y="39" width="14" height="14" transform="rotate(45 420 46)" fill="#fff" stroke="#b3261e" stroke-width="2"/>
<text x="420" y="132" text-anchor="middle" font-size="13" font-weight="600" fill="currentColor">Risk</text>
<circle cx="540" cy="92" r="17" fill="#ecebe6" stroke="#9a9a94" stroke-width="2"/>
<text x="540" y="97" text-anchor="middle" font-size="14" font-weight="700" fill="#5a5a55">5</text>
<rect x="533" y="39" width="14" height="14" transform="rotate(45 540 46)" fill="#fff" stroke="#b3261e" stroke-width="2"/>
<text x="540" y="132" text-anchor="middle" font-size="13" font-weight="600" fill="currentColor">Verification</text>
<text x="540" y="147" text-anchor="middle" font-size="13" font-weight="600" fill="currentColor">and evidence</text>
<circle cx="660" cy="92" r="17" fill="#ecebe6" stroke="#9a9a94" stroke-width="2"/>
<text x="660" y="97" text-anchor="middle" font-size="14" font-weight="700" fill="#5a5a55">6</text>
<rect x="653" y="39" width="14" height="14" transform="rotate(45 660 46)" fill="#fff" stroke="#b3261e" stroke-width="2"/>
<text x="660" y="132" text-anchor="middle" font-size="13" font-weight="600" fill="currentColor">Release and</text>
<text x="660" y="147" text-anchor="middle" font-size="13" font-weight="600" fill="currentColor">PMS</text>
</svg>
<p class="small muted">Greenfield: six stages. Gates on stages 2, 4, 5 and 6.</p>
<svg viewBox="0 0 720 170" role="img" aria-label="Retrofit route: steps A to G" style="width:100%;max-width:720px;height:auto;font-family:inherit">
<title>Retrofit route: steps A to G</title>
<line x1="60" y1="92" x2="660" y2="92" stroke="#9a9a94" stroke-width="2"/>
<circle cx="60" cy="92" r="17" fill="#ecebe6" stroke="#9a9a94" stroke-width="2"/>
<text x="60" y="97" text-anchor="middle" font-size="14" font-weight="700" fill="#5a5a55">A</text>
<rect x="53" y="39" width="14" height="14" transform="rotate(45 60 46)" fill="#fff" stroke="#b3261e" stroke-width="2"/>
<text x="60" y="132" text-anchor="middle" font-size="13" font-weight="600" fill="currentColor">Gap</text>
<text x="60" y="147" text-anchor="middle" font-size="13" font-weight="600" fill="currentColor">assessment</text>
<circle cx="160" cy="92" r="17" fill="#ecebe6" stroke="#9a9a94" stroke-width="2"/>
<text x="160" y="97" text-anchor="middle" font-size="14" font-weight="700" fill="#5a5a55">B</text>
<rect x="153" y="39" width="14" height="14" transform="rotate(45 160 46)" fill="#fff" stroke="#b3261e" stroke-width="2"/>
<text x="160" y="132" text-anchor="middle" font-size="13" font-weight="600" fill="currentColor">Baseline</text>
<circle cx="260" cy="92" r="17" fill="#ecebe6" stroke="#9a9a94" stroke-width="2"/>
<text x="260" y="97" text-anchor="middle" font-size="14" font-weight="700" fill="#5a5a55">C</text>
<rect x="253" y="39" width="14" height="14" transform="rotate(45 260 46)" fill="#fff" stroke="#b3261e" stroke-width="2"/>
<text x="260" y="132" text-anchor="middle" font-size="13" font-weight="600" fill="currentColor">Purpose and</text>
<text x="260" y="147" text-anchor="middle" font-size="13" font-weight="600" fill="currentColor">class</text>
<circle cx="360" cy="92" r="17" fill="#ecebe6" stroke="#9a9a94" stroke-width="2"/>
<text x="360" y="97" text-anchor="middle" font-size="14" font-weight="700" fill="#5a5a55">D</text>
<rect x="353" y="39" width="14" height="14" transform="rotate(45 360 46)" fill="#fff" stroke="#b3261e" stroke-width="2"/>
<text x="360" y="132" text-anchor="middle" font-size="13" font-weight="600" fill="currentColor">Requirements</text>
<text x="360" y="147" text-anchor="middle" font-size="13" font-weight="600" fill="currentColor">and SOUP</text>
<circle cx="460" cy="92" r="17" fill="#ecebe6" stroke="#9a9a94" stroke-width="2"/>
<text x="460" y="97" text-anchor="middle" font-size="14" font-weight="700" fill="#5a5a55">E</text>
<rect x="453" y="39" width="14" height="14" transform="rotate(45 460 46)" fill="#fff" stroke="#b3261e" stroke-width="2"/>
<text x="460" y="132" text-anchor="middle" font-size="13" font-weight="600" fill="currentColor">Risk</text>
<circle cx="560" cy="92" r="17" fill="#ecebe6" stroke="#9a9a94" stroke-width="2"/>
<text x="560" y="97" text-anchor="middle" font-size="14" font-weight="700" fill="#5a5a55">F</text>
<rect x="553" y="39" width="14" height="14" transform="rotate(45 560 46)" fill="#fff" stroke="#b3261e" stroke-width="2"/>
<text x="560" y="132" text-anchor="middle" font-size="13" font-weight="600" fill="currentColor">Test</text>
<text x="560" y="147" text-anchor="middle" font-size="13" font-weight="600" fill="currentColor">evidence</text>
<circle cx="660" cy="92" r="17" fill="#ecebe6" stroke="#9a9a94" stroke-width="2"/>
<text x="660" y="97" text-anchor="middle" font-size="14" font-weight="700" fill="#5a5a55">G</text>
<rect x="653" y="39" width="14" height="14" transform="rotate(45 660 46)" fill="#fff" stroke="#b3261e" stroke-width="2"/>
<text x="660" y="132" text-anchor="middle" font-size="13" font-weight="600" fill="currentColor">Close</text>
<text x="660" y="147" text-anchor="middle" font-size="13" font-weight="600" fill="currentColor">gaps</text>
</svg>
<p class="small muted">Retrofit: seven steps. A gate on every step.</p>
</div>

### The stages and their checks

Greenfield:

1. **Organisation and device set-up**: our economic operator role, the legal manufacturer, the device description, the expected lifetime and the device team.
2. **Intended purpose and classification**: intended purpose, users and patient population, the class in every market the device is placed on, the classification rationale and the IEC 62304 software safety class.
3. **Requirements, design and software items**: the software items, an effective design document and GSPR checklist, linked SOUP and the current software version.
4. **Hazards, controls and residual risk**: hazards in the risk register, a control on every hazard, every control verified, every residual risk accepted and an effective risk management file.
5. **Verify, validate and show performance**: effective verification and validation evidence, effective clinical evaluation and usability evidence, and no open problem with patient-safety impact.
6. **Release, technical file and surveillance**: labelling and IFU, the PMS schedule and plan, the declaration of conformity, a technical file with no completeness errors and an approved build.

Retrofit:

- **A. Gap assessment**: an effective document for this device with "gap assessment" in its title. Record the gap assessment as a document with that in its title so the check finds it.
- **B. Freeze and baseline the release**: the current software version recorded as the baseline, at least one change request recorded (change control in use), and the set-up checks from greenfield stage 1.
- **C. Reconstruct intended purpose and classification**: the same checks as greenfield stage 2.
- **D. Reconstruct requirements, design and SOUP**: the same checks as greenfield stage 3.
- **E. Reconstruct the risk file and check controls**: the same checks as greenfield stage 4; every control verified is also a gate check.
- **F. Test evidence against the baseline**: effective verification and validation evidence, and no open problem with patient-safety impact.
- **G. Close the gaps and assess regulatory position**: clinical evaluation and usability evidence, and the release checks from greenfield stage 6.

Checks marked **gate check** are the ones the stage's approver gate relies on. Under each stage, the gate line names the gate and says whether it is approved (by whom and when), awaiting sign-off, or waiting for its checks.

Documents count only once they are effective and tagged with the right technical file section, as for the technical file build. A check that depends on a document stays open while the document is a draft or in review.

### Checks and sign-off

A gate can't be signed until its gate checks pass. On **My tasks**, a gate card whose checks don't pass shows an alert, **Can't be signed yet**, listing each failing check with a link to fix it, and no signing form. The email the approver gets when a gate opens lists the same failing checks. Once the checks pass, the card shows **Gate checks pass** and the signing form. Passing checks show that the pieces exist; the approver still judges whether they are adequate before signing.

A gate that is already approved stays approved if a check later stops passing: its diamond turns dashed and its card says the checks no longer pass, so you can look at what changed.

The route doesn't decide whether a technical file can be approved: the **Technical file** panel does.

The stages follow the SaMD documentation guide: greenfield stage 1 is phase 0, stage 2 phase 1, stage 3 phase 2, stage 4 phase 3, stage 5 phases 4 and 5, and stage 6 phase 6; retrofit steps A to G follow the guide's retrofit steps. The panel doesn't score individual documents for the gap assessment itself.

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
signature in the audit trail. Each gate card also says whether the gate's checks on the device page pass, and
lists any that don't. While a gate's checks don't pass it can't be signed: the card shows an alert with the failing checks instead of the signing form, and the gate-open email lists them too. The next approver is emailed when a gate opens. Nothing else on the board can be dragged or moved by hand: cards change
when the underlying record, document or gate changes.

## People

**People** lists everyone on the teams of the devices you can see, with their roles on each device. It also lists people who hold an organisation-wide role (set by an administrator in Admin); those are read-only here.

Device admins and QA on a device can, for each person on that device's team:

- **Change roles:** tick or untick roles and save. Untick every role to keep someone on the team with no role.
- **Remove from team:** this revokes their access to the device. Their past records and signatures are kept.
- **Add a person:** choose someone with an account who is not yet on the team, then their roles and responsibility.

You can't change your own roles, and a device must keep at least one Device admin or QA on its team. Every change is recorded in the audit trail with who made it and when.

Only a **QMS admin** can add, change or remove the **Device admin** role. A Device admin can still manage the other roles and the people on the team, but cannot appoint another Device admin or remove one. The same applies to invitations and account requests.

## Acting as one role

If you hold more than one role, the **Acting as** list in the top bar lets you work as one of them. Choose a role and the app works as that role only: what you can do, the functions listed on the dashboard, and the team pages all follow that role. Choose **All my roles** to go back to everything you hold.

The choice can only narrow what you can do. You can't choose a role you don't hold, and the choice is kept for your browser session only.
