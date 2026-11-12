# Documenting a software medical device (SaMD)

This guide is for an organisation that makes software intended for a medical purpose and uses
SAMD_QMS to hold its quality records. It covers two starting points:

- **Greenfield:** the device is not yet on the market and documentation starts with the project.
- **Retrofit:** the device is already in use or in development, and its documentation is partly
  missing, scattered, or never went through a formal quality system.

It is a practical map, not legal advice. Have your notified body, regulatory consultant or
regulator-facing lead confirm classification, the route to market and the evidence you rely on.
Check the current versions of every standard and guidance cited here before you use them, since
several have been revised or are being revised.

---

## 1. Ground rules

1. **Start from the intended purpose.** Everything else follows from what the software is
   claimed to do for patients or users: its intended purpose, intended users, intended
   patient population, intended use environment and contraindications. Record these first, in
   the Device record (`intended_purpose`, `intended_users`, `patient_population`,
   `contraindications`).
2. **Decide whether it is a medical device at all.** Software is a medical device when its
   manufacturer intends it to be used for a medical purpose (diagnosis, prevention, monitoring,
   prediction, prognosis, treatment or alleviation of disease or injury, and similar), and it
   does not act only on another device's hardware or as a pure administrative or storage tool.
   The IMDRF "Software as a Medical Device" definition is the common reference. Record the
   reasoning in `classification_rule`.
3. **Classify before you build the evidence.** Classification sets how much evidence is
   needed. Under EU MDR Rule 11 (Annex VIII), software that provides information used to take
   decisions with diagnosis or therapeutic purposes is at least Class IIa, and higher where the
   decision could cause death or irreversible deterioration, or serious deterioration or
   surgical intervention. MDCG 2019-11 explains how to apply Rule 11. The UK MDR 2002 and the
   FDA each have their own classification. The Device record holds all three
   (`eu_classification`, `uk_classification`, `us_classification`), plus the
   `software_safety_class` that IEC 62304 uses.
4. **Keep records honest.** Do not backdate. A reconstructed record is labelled as
   reconstructed, with the date it was written and the evidence it is based on. The
   electronic-signature trail in SAMD_QMS is designed to show this, and an auditor will
   look for it.
5. **Change control starts on day one.** Once a version is released, every change goes through
   a Change Request. For a retrofit, change control starts at the moment you begin
   reconstruction.

---

## 2. Document map

The list below is the standard set for a software device. The "eQMS home" column shows where
each item lives in SAMD_QMS. Items marked *Device* are created per device. Items marked *QMS* are
organisation-wide and shared by every device.

| Document | Standard / reference | eQMS home |
|---|---|---|
| Quality management system manual and procedures | ISO 13485 §4.2 | *QMS* Documents (procedures, tagged to the technical file section) |
| Device description, intended purpose, classification rationale | EU MDR Annex II §1, Annex VIII; UK MDR; FDA | *Device* record fields; technical file section 1 |
| Software requirements specification (SRS) and software design specification (SDS) | IEC 62304 §5.2, §5.3 | *Device* Documents tagged to the software section; Device `software_items` |
| Software architecture, including SOUP and interfaces | IEC 62304 §5.3 | *Device* Documents; `software_items`; *Device* SOUP (Supplier, SoupItem) |
| Risk management file (hazards, causes, harms, controls, residual risk) | ISO 14971:2019; IEC 62304 §7 | *Device* Hazards and RiskControls |
| Usability / human factors file | IEC 62366-1 | *Device* Documents |
| Verification and validation plan, protocols and reports | IEC 62304 §5.5–5.7; EU MDR Annex II §6 | Documents, plus `run_oq` evidence for automated requirements |
| Known anomalies (Problem Reports) | IEC 62304 §5.8.3 | Problem Reports, shown in the technical file gaps check |
| Release history and configuration (versions, build records) | IEC 62304 §8; MDR Annex II §6.1 | Change Requests grouped by `fix_version`; TechnicalFileBuild |
| Cybersecurity documentation (threat model, SBOM, security risk, vulnerability handling) | IEC 81001-5-1; FDA cybersecurity guidance | Hazards for security risk; SOUP; Documents |
| Clinical evaluation and performance evidence | EU MDR Art. 61, Annex XIV; MDCG 2020-1 (clinical evaluation of software) | Documents (clinical evaluation report) |
| Post-market surveillance plan and reports | EU MDR Art. 83–86, Annex III | *Device* PMS schedule; PMS activities; complaints; incidents |
| Post-market clinical follow-up (where required) | EU MDR Art. 84 | Documents |
| Labelling, instructions for use, UDI | EU MDR Art. 10(11), Annex I §23; UK MDR; FDA labelling rules | Documents; Device `basic_udi_di` |
| Declaration of conformity / UKCA / FDA submission | EU MDR Annex IV; UK MDR; FDA 510(k) or De Novo | Documents; `approved_body`, `regulatory_status` |
| Training records | ISO 13485 §6.2 | Training requirements and assignments |
| Supplier controls (including SOUP suppliers) | ISO 13485 §7.4 | Suppliers |
| Records of nonconforming product, CAPA, complaints, internal audits, management review | ISO 13485 §8 | Records of those types |

Check the exact sections against the current editions. The eQMS column is a pointer, not a
claim of compliance. The compliance matrix in `docs/iso13485-compliance-matrix.md` records which
ISO 13485 clauses the application covers and which an organisation must cover by procedure.

---

## 3. Starting from scratch (greenfield)

Work through these phases in order. Each phase ends with a review and a sign-off, not just a
file in a folder.

### Phase 0: Set up the device and the organisation (week 1)

- Complete the organisation profile: economic operator roles (manufacturer, authorised
  representative, importer, distributor) and the role each device plays.
- Create the Device with its name, code, and basic description.
- Assign the device team and roles. Keep at least one Device admin and at least one QA person.
- Decide the expected lifetime of the device and the records you must keep (ISO 13485 §4.2.5).

### Phase 1: Intended purpose and classification

- Write the intended purpose as a single statement that names the user, the patient group, the
  clinical context and the output. Enter it in `intended_purpose`.
- Work through the classification rules for each market. Record the class and the reasoning in
  `classification_rule`.
- Decide the `software_safety_class` (A, B or C under IEC 62304), based on the possible harm
  from a software failure. Record the reasoning with the risk file.
- Have the classification reviewed. Record the review as a signed Document or Change Request.

### Phase 2: Requirements and design

- Write the software requirements (SRS): functional, performance, interface, security,
  usability and regulatory requirements. Each requirement needs an ID, a rationale and a way to
  test it.
- Write the design (SDS): architecture, modules, data flow, interfaces, SOUP.
- Add the software items to the Device (`software_items`), so each item has an owner in the
  record.
- Create the **URS** list for the QMS itself if the device team also uses SAMD_QMS to manage the
  project. See the URS section of `docs/developer-guide.md`.

### Phase 3: Risk management (ISO 14971, starting at concept)

- Identify hazards for the intended use and for reasonably foreseeable misuse. Include software
  faults, wrong outputs, data errors, cybersecurity, and use errors (from the usability file).
- For each hazard, estimate severity and probability, then record the controls and the residual
  risk. Record each control with its verification.
- Link each control to the requirement that implements it. Hazards without controls, and
  controls without verification, are the most common findings in audits.
- Keep the risk file current. Review it at each design review and after each complaint or
  incident.

### Phase 4: Implementation, verification and validation

- Implement against the SRS and SDS. Keep unit, integration and system test records.
- Run verification against each requirement. Automated tests can be traced to requirements and
  run as objective evidence (`run_oq` does this for SAMD_QMS itself). Manual tests are recorded
  as protocols.
- Validate the device with users in its intended use environment, including the usability
  evaluation.
- Record every known anomaly as a Problem Report, with its impact and whether the release goes
  ahead.

### Phase 5: Clinical and performance evidence

- Write the clinical evaluation plan and report. For software, performance evidence is often the
  core of the evidence: accuracy, sensitivity, specificity, reproducibility on representative
  datasets, plus any clinical data.
- Document the dataset: source, size, representativeness, labelling process, and how it was kept
  separate from training data (if the device uses machine learning).
- Link the clinical evidence to the intended purpose and the risk file.

### Phase 6: Release, technical file and post-market

- Freeze the release. Use TechnicalFileBuild to create the technical file from live data. The
  completeness check lists gaps by section. Resolve every error before the build is approved.
- Approve the build with a QA signature.
- Set up the PMS schedule. Plan complaints handling, vigilance reporting (EU MDR Art. 87, UK and
  FDA equivalents), trend analysis, and periodic safety update reports where they apply.
- Record every post-market change through Change Requests, and re-run the affected verification
  and risk review.

---

## 4. Retrofitting an existing device

The aim is to reach the same evidence set without pretending the history is cleaner than it is.
Expect to spend more time on the gap assessment than on writing.

### Step 1: Gap assessment (2–4 weeks)

Take the document map in section 2 and score each item:

- **Exists and is current:** record its location and its version.
- **Exists but is out of date or unsigned:** record what is wrong.
- **Exists only in code, tickets or someone's head:** record where the knowledge is.
- **Does not exist:** record it as a gap.

Sort the gaps by safety impact. The first priorities are:

1. Intended purpose and classification, because every other decision depends on them.
2. Risk file, especially hazards that have no control or no verification.
3. Known anomalies: open bugs and incidents in the tracker.
4. SOUP list and its risk, including open-source libraries and cloud services.
5. Release history: which versions reached users, and what changed in each.
6. Verification evidence for the current release.
7. Clinical and performance evidence.
8. Everything else.

Record the gap assessment as a Document in the QMS. It is the starting point for the
remediation plan and the first item an auditor will ask for.

### Step 2: Freeze and baseline the current release

- Identify the release in production (version, build and commit). Record it as the baseline.
- Start a Change Request for every change from now on. Nothing ships without a record.
- Create a Device record for the existing product even if the record is partly empty. Mark
  what is reconstructed in the text.

### Step 3: Reconstruct the core documents

- **Intended purpose, users, population, contraindications:** reconstruct from the labelling,
  marketing material and the design history. Record that it was reconstructed, and have the
  current management sign it.
- **Software requirements and design:** reconstruct from the code, existing tests, API
  documentation and architecture diagrams. Label the reconstructed version as such. Each
  reconstructed requirement should be traceable to code or a test.
- **Risk file:** reconstruct the hazards from the intended purpose, the known incidents and the
  code paths. Then review each control and check it against the code. Where a control is
  missing, add a Change Request.
- **SOUP:** generate the list from the dependency manifests (for example `requirements.txt`,
  `package-lock.json`, container base images). Add supplier, version, known anomalies, and risk
  assessment for each item. Record the source and the date of the scan.

### Step 4: Establish verification evidence

- Run the existing test suite against the baseline and record the results. Where tests are
  missing for a requirement, write them and trace them.
- For each automated test, link it to its requirement. Keep the run output as evidence for
  the release.
- Where you cannot prove a requirement works, record it as a known limitation in the risk file
  and the labelling, and schedule the work.

### Step 5: Close the gaps by priority

- Use Change Requests for each remediation. Each one should say what it changes, the risk it
  addresses, the verification, and the release that carries it.
- Make changes in release order, not all at once. Each release should leave the documentation
  more complete than the last.

### Step 6: Assess the regulatory position

- If the device was placed on the market without the evidence the current classification
  needs, speak to your regulator or notified body early. The route to compliance can include
  a conformity assessment, a field safety corrective action, or both. Do not rely on this guide
  for that decision.
- Record the outcome of the assessment, and the decisions that came from it.

### Things to avoid in a retrofit

- Backdating records or inserting old signatures.
- Writing an "ideal" history that the code and the release record do not support.
- Treating a passing test suite as the full verification, when it does not test the intended use.
- Leaving the risk file as a list of generic hazards with no controls.
- Ignoring SOUP, especially hosted services and third-party models.

---

## 5. Working in SAMD_QMS

- **Devices:** one Device per software product, or per product variant if the classification or
  intended purpose differs.
- **Documents:** tag each Document with its technical file section, so the technical file build
  picks it up.
- **Hazards and RiskControls:** link controls to the requirements that implement them, and to
  the tests that verify them.
- **SOUP:** keep the SoupItem list current for each device. Link each item to its supplier.
- **Change Requests:** record every change, with `fix_version` set to the release that carries it.
- **Problem Reports:** record every known anomaly, so the release history and the technical file
  show the known residual issues.
- **TechnicalFileBuild:** run it at each release candidate. Fix the completeness errors first.
- **PMS:** set the schedule per device, and link complaints and incidents to the relevant hazards.
- **Documentation route:** each device's page shows the six stages of this guide as checks worked
  out from the QMS's own data, with gates marked and a link to fix each open check. Stage 1 is
  phase 0, stage 2 phase 1, stage 3 phase 2, stage 4 phase 3, stage 5 phases 4 and 5, and stage 6
  phase 6. It shows that the pieces exist, not that they are adequate, and it doesn't score
  documents for a retrofit gap assessment.

---

## 6. Checklist

Use this before a release or an audit.

- [ ] Intended purpose, users, population and contraindications are stated and signed.
- [ ] Classification is recorded for each market, with reasoning, and reviewed.
- [ ] Software safety class is recorded.
- [ ] Requirements (SRS) exist, are versioned, and trace to tests.
- [ ] Design (SDS) exists, and software items are listed on the Device.
- [ ] Risk file has a hazard for each identified harm, with controls, verification and residual risk.
- [ ] SOUP list is current, with suppliers and known anomalies.
- [ ] All known anomalies are recorded as Problem Reports, and the release decision records them.
- [ ] Verification evidence is run against the release, and the results are kept.
- [ ] Usability evidence exists for the intended users and environment.
- [ ] Clinical and performance evidence matches the intended purpose and the risk file.
- [ ] Technical file build has no completeness errors and is approved with a signature.
- [ ] PMS schedule is set, with complaints and incident handling in place.
- [ ] Every change since the baseline has a Change Request.
