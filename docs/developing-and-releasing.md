# Developing and releasing SAMD_QMS

This guide covers the everyday loop on your development machine, and how a change reaches
staging and then production. For setting up a new server, see
[Deploying on a Linux VM](deploy-linux-vm.md). For the full reference, see
[deployment.md](deployment.md).

The rule that shapes everything: **production runs only a tagged, tested release**. The
deploy playbook refuses `main`, `latest` and any unpinned version, so every change follows the
same route: branch, review, merge, tag, staging, production.

---

## 1. One-time set-up on your machine

You need Docker with the Compose plugin, `make`, and `git`. For running the checks without Docker,
also Python 3.13.

```bash
git clone https://github.com/your-org/eQMS.git && cd eQMS
make dev        # build and start the dev stack: app http://localhost:8000, mail http://localhost:8025
make demo       # demo devices and users; sign in as engineer_person, qa_person, qa2_person or cso_person (password demo-pass-123)
```

To work without Docker (for example from PyCharm), see *Without Docker* in
[deployment.md](deployment.md#without-docker-virtualenv-eg-in-pycharm).

### Update an existing dev instance after code changes

When `main` has moved on (someone merged a pull request, or you switched branches), bring your
dev instance up to date. Your data is kept unless you choose otherwise.

```bash
git switch main && git pull          # or: git switch your-branch
make dev                             # rebuilds the image and starts the stack
```

- **Code** in the source folder is picked up on save, but a change to `requirements.txt` or the
  Dockerfile needs the rebuild that `make dev` does.
- **Database migrations** from new code run automatically when the app container starts. Check
  them with `make manage CMD="showmigrations qms"`; unapplied migrations show as `[ ]` instead
  of `[X]`.
- **`make dev` follows the app log and does not return.** Press Ctrl+C to stop following; the
  containers keep running. Use `make logs` to follow the log again.
- **Demo data is not refreshed.** `make demo` refuses to run on a database that already has
  devices or documents. To get the demo as it is in the current code, start again:

  ```bash
  make dev-reset                     # deletes the dev database, files and backups
  make dev                           # in one terminal; leave it running
  make demo                          # in a second terminal, once the app is up
  ```

- **Port in use.** `make dev` needs ports 8000 (app), 8025 (mail) and 5432 (PostgreSQL) to be
  free. If it reports "port is already allocated", find the container holding the port with
  `docker ps` and stop it (`docker stop <name>`), or stop the other project's stack.
- **Check it works:** open http://localhost:8000, sign in as `engineer_person` (password
  `demo-pass-123`), and check the page you changed.

---

## 2. The everyday loop

Work on a branch, never on `main`:

```bash
git switch -c feature/short-description main
```

While you work:

| Task | Command |
| --- | --- |
| See the app change as you edit | Nothing to do: the source folder is mounted and reloads on save |
| Watch the app's log | `make logs` |
| A Django shell | `make shell` |
| Run a management command | `make manage CMD="showmigrations qms"` |
| Run the test suite (PostgreSQL) | `make test` |
| Run the browser tests too | `make ui` (use `make ui HEADED=1` to watch them) |
| Lint shell scripts, Compose and Ansible | `make check` |
| Create database migrations after a model change | `make manage CMD="makemigrations qms -n short_name"`, then commit the new file |
| Reset your dev data | `make dev-reset` (deletes the dev database, files and backups) |
| Stop the stack (keeps data) | `make dev-down` |

Two rules from the project's validation practice apply to every change:

- **Tests and requirements travel together.** A new behaviour gets a test, and the test is traced
  to a user requirement in `qms/validation.py`. `make oq NAME="Your Name"` runs the operational
  qualification and writes the evidence to `oq_evidence/`. CI fails if a test is not traced.
- **Help and docs travel together.** Update the in-app help in `qms/help/` for anything a user sees,
  and the developer guide for anything a developer needs to know. `make test` includes the help
  tests, which fail when a page or form field has no help.

Before you open a pull request, run the whole check on your machine:

```bash
make test && make check
```

---

## 3. Open a pull request

```bash
git push -u origin feature/short-description
gh pr create --base main --title "Short title" --body-file -
```

CI runs on every pull request: the checks, the full suite on PostgreSQL 16, the operational
qualification (OQ), infrastructure checks, and an image build with a smoke test. The pull request
can merge only when the required checks pass. If "Tests and OQ evidence" fails, open its log in
GitHub (`gh run view --log-failed`), fix the cause on your branch, and push again.

Merge when CI is green. Merging to `main` builds the image again and pushes it as `:main` and
`:sha-<commit>`, and refreshes the README badges.

---

## 4. Release candidate to staging

Staging is a second server with the same set-up as production, used to rehearse a release with the
real migrations, backups, certificates and sign-in before production sees it.

```bash
git switch main && git pull --ff-only
git tag v1.1.0-rc1 && git push origin v1.1.0-rc1
```

CI pushes the image as `:1.1.0-rc1`. Deploy it to staging:

```bash
make deploy ENV=staging VERSION=1.1.0-rc1
```

On staging, check what changed, using the list in [section 6](#6-checks-before-production):

- Sign in with a real account, and do the workflows the release touches.
- Check that the migrations applied: `scripts/remote.sh -e staging status`.
- Check the certificate and the security headers (see [deploy-linux-vm.md](deploy-linux-vm.md#5-check-the-certificate)).
- Download the OQ evidence for the tag from the CI run's artifacts, and file it with the release.

If something is wrong, fix it on a branch, merge it, and tag a new candidate (`v1.1.0-rc2`).

---

## 5. Release to production

When staging is right, tag the final version from the same commit you tested on staging:

```bash
git tag v1.1.0 && git push origin v1.1.0
```

Wait for CI to finish the `v1.1.0` run (it pushes the image as `:1.1.0`), then deploy:

```bash
make deploy ENV=production VERSION=1.1.0
```

The playbook refuses placeholder secrets and production without off-site backups and the signer
rule. It then backs up **before changing anything**, applies the migrations, starts the new
containers, waits until `/healthz` answers over HTTPS, verifies the audit trail, and records the
deployment in `DEPLOYMENTS.log` on the server.

Right after the deploy, check the site and the admin tunnel:

```bash
curl -s https://qms.example.org/healthz            # status "ok" and the version 1.1.0
scripts/remote.sh -e production status             # containers and their health
```

File the `v1.1.0` OQ evidence artifact as the release record.

---

## 6. Checks before production

| Check | Where |
| --- | --- |
| CI green on the tag (tests, OQ, image build) | GitHub Actions run for the tag |
| The same commit ran on staging for the rehearsal | `DEPLOYMENTS.log` on staging, and the tag |
| Migrations and their effect on data | Read `qms/migrations/` for the release; the deploy takes a backup first |
| Release notes: what changed for users, and what they must do | Write them into the pull request or a release note |
| Recent backup exists and restores | `make restore-test` (restores the latest backup into a scratch database) |
| Someone who will use the change has seen it on staging | Your sign-off; the QA release record |

---

## 7. If production goes wrong

**Roll back to the previous release** by deploying its version. The playbook backs up first again:

```bash
make deploy ENV=production VERSION=1.0.0
```

Rolling back the code does **not** reverse database migrations. If the new release ran migrations
that the old one cannot read, restore the pre-deploy backup that the deploy took (see
[Backups and restore](deployment.md#backups-and-restore)) before you roll back the code.

Record the incident and the fix as a QMS record. Fix forward on a branch, and release a new tag
rather than editing a tagged release.

---

## 8. Quick reference

| I want to... | Do this |
| --- | --- |
| Start developing | `make dev`, `make demo`, then a branch from `main` |
| Update my dev instance after pulling code | `git pull`, then `make dev` (see *Update an existing dev instance* in section 1) |
| Reload the demo data as the current code has it | `make dev-reset`, `make dev`, then `make demo` |
| Check my change | `make test && make check` |
| Get it reviewed and tested by CI | Pull request to `main` |
| Rehearse a release | Tag `vX.Y.Z-rcN`, then `make deploy ENV=staging VERSION=X.Y.Z-rcN` |
| Release to production | Tag `vX.Y.Z`, then `make deploy ENV=production VERSION=X.Y.Z` |
| Undo a release | `make deploy ENV=production VERSION=<previous>` (restore the database first if migrations ran) |
| See what is running | `scripts/remote.sh -e production status`, `DEPLOYMENTS.log` on the server |
