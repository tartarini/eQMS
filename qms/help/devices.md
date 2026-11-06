Each medical device has its own records, risk file, post-market surveillance (PMS) schedule, SOUP list, software items and technical file. QMS-wide procedures, training, suppliers and roles are shared by every device.

## Choose a device

Pick a device in the menu at the left of the top bar. Lists, the dashboard and the risk matrices then show only that device, and new records, hazards and documents default to it. Choose **All devices** to see everything. Every list has a **Device** column so you can always tell them apart.

## Device teams

Your role (Engineer, QA or Clinical Safety Officer) says what you can do; your device teams say which devices you can do it on. You can be on as many teams as your work needs, and the device menu lists only your devices.

- You see, and can act on, only the records, risks, device documents and technical files of your teams. QMS-wide documents and your training are visible to everyone.
- Emails and training for a device go only to its team.
- People with **All-device access** (for example the head of quality or an auditor) see every device and the full **Audit** page.
- **QA on a team** adds and removes members on the device's page under **Team**. Removing someone keeps their past records and signatures. The person who creates a device joins its team automatically, and a device must always keep at least one member.
- A record's linked hazards must belong to the same device, even if you're on several teams.

## Add a device

QA only.

1. **Devices → New device**.
2. Enter the name, a short code (for example HRT1) and the regulatory particulars: intended purpose, users and patients, classification and rationale, IEC 62304 software safety class, Basic UDI-DI, manufacturer, markets and standards applied. You can complete these later; they form section 1 of the technical file.
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
