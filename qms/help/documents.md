Every controlled document (SOP, work instruction, policy, plan, specification, form, report) has a number such as SOP-001 and a series of versions. Only one version is **Effective** at a time, and that is the one people must follow.

A document is either **QMS-wide** (no device: procedures and policies that apply to every device, visible to everyone) or belongs to **one device** (visible only to its team, and can be placed in its technical file).

| Version status | Meaning |
| --- | --- |
| Draft | Being written; the file and summary can still change |
| In review | Submitted; content is frozen |
| Approved | Signed by QA, waiting to go live |
| Effective | The current version; training is assigned |
| Superseded | Replaced by a newer effective version |
| Obsolete | Withdrawn |

## Create or revise a document

1. **Documents → New document** for a new one, or open an existing document and click **New version**.
2. Enter the version number (the next major version is suggested), a summary of what changed and why, and upload the file. Link the Change Request that authorised the revision, if there is one.
3. Click **Submit for review**. QA is emailed.
4. QA either **approves and signs** (the author can't approve their own version) or **returns it for changes** with a comment.
5. QA clicks **Make effective today**. The previous version becomes Superseded and training is assigned.

Only one revision can be in progress per document. If the file on the server changes after upload, approval is refused and the version must be returned for a fresh upload.

## Periodic review and withdrawal

Each document has a review period (24 months by default). As the review date approaches it appears on the dashboard and in reminder emails. If nothing needs changing, QA records a signed **Periodic review: no change needed**, which resets the date; otherwise create a new version. To retire a document, QA uses **Withdraw document** with a signed reason.

## Import and export

**Export folder (zip)** downloads every effective document you can see as a folder per document, under its device and type. Each folder holds a markdown file with the document's details and text (or a pointer to its file) and the controlled file itself. The download also includes an index of all documents and a manifest of file checksums.

**Import markdown** brings markdown files back in. Each file starts with a front-matter block between two `---` lines:

```
---
title: Calibration of test rigs
type: SOP
device: SKN
description: How the test rigs are calibrated.
---
Text of the document in markdown.
```

A file without a `number` creates a new document with a draft first version. A file with the `number` of an existing document (as exported) adds a draft revision. Imports are checked against your device teams, and each new document or revision is recorded in the audit trail like any other.

A server administrator can also link a git repository that is kept in sync with the QMS: each night the scheduler updates the clone, commits the changes (only when something changed), and pushes them if configured (`QMS_DOCS_GIT_REPO`, `QMS_DOCS_GIT_PUSH`). A document that is no longer effective is removed from the repository; its versions stay in the QMS.

