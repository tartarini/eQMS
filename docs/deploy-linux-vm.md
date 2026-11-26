# Deploying SAMD_QMS on a Linux VM with Let's Encrypt

This guide takes a new virtual machine from nothing to a working production site, with a
certificate from Let's Encrypt that renews itself. Replace `qms.example.org` with your own name
throughout. You can publish the site at the root of that name or under a path such as `/qms`
(section 1 explains the choice).

Two routes, depending on the operating system:

| Operating system | How the server is prepared | How the release is deployed |
| --- | --- | --- |
| **Ubuntu 22.04 or 24.04**, or Debian 12 | Automatically, by `make provision` (Ansible) | `make deploy` (Ansible) |
| **Red Hat Enterprise Linux 9 or 10** | Automatically, by `make provision` (Ansible) | `make deploy` (Ansible) |
| Rocky Linux, AlmaLinux, other rebuilds | By hand, using the steps in [section 6](#6-rocky-linux-almalinux-and-other-rebuilds-by-hand) | `make deploy` (Ansible), from your workstation |

`make provision` refuses any other operating system. Rocky and AlmaLinux are not covered by the
playbook, so they are prepared by hand. Everything after that is the same.

Docker Engine's support for RHEL 10 is not confirmed by Docker at the time of writing. Check the
[Docker support matrix](https://docs.docker.com/engine/install/rhel/) before you use RHEL 10 in
production.

The rest of the stack is described in [deployment.md](deployment.md): Apache terminates HTTPS,
gunicorn runs the app, PostgreSQL holds the data, and a scheduler runs the daily jobs and backups.

---

## 1. Before you start

### Choose the address

Pick one of two addresses. Server, certificate and firewall steps are the same for both. Only
the address and one setting differ.

| Option | Address | When to choose it |
| --- | --- | --- |
| **A. The root of a name** (default) | `https://qms.example.org/` | The VM serves SAMD_QMS and nothing else. No path setting is needed. |
| **B. A path on a name** | `https://qms.example.org/qms/` | You want SAMD_QMS under a path of a name your organisation already uses, such as `vht.shef.ac.uk/qms`. The root address redirects to `/qms/`. |

For option B, create a host variables file before you deploy. Do this on your workstation, not on
the server, in a terminal opened at the root of the repository (the folder that contains
`Makefile`, `docs/` and `deploy/`). The commands use relative paths, so run them from there:

```bash
cd /path/to/SAMD_QMS            # the repository root on your workstation
mkdir -p deploy/ansible/host_vars
printf 'qms_url_prefix: "/qms"\n' > deploy/ansible/host_vars/qms.example.org.yml
```

Check that the file name matches the host name on the inventory line you write in
[section 3.1](#31-describe-the-server) exactly, character for character. Replace
`qms.example.org` in the file name with that host name. If the two differ, Ansible ignores the
file and the site is published at the root of the name.

Option B changes these details, covered in [section 4](#4-first-start):

- Sign-in callbacks at each provider are `https://qms.example.org/qms/accounts/<provider>/login/callback/`.
- The health check and the uptime monitor use `https://qms.example.org/qms/healthz`.
- Administration is `https://localhost:8443/qms/admin/` through the SSH tunnel.
- Use the same address everywhere in your own notes: `scripts/remote.sh health` and `status` read the path from the server.

Option B needs ports 80 and 443 on this VM for SAMD_QMS alone, as in option A. If another website
already answers on that name's ports 80 and 443 (on another machine or behind a proxy), the proxy
must forward `/qms/` to this VM. This guide does not set that up. Ask your IT team, or see
[Publishing under a path](deployment.md#publishing-under-a-path-eg-httpsvhtshefacukqms).

**The virtual machine**

- 2 vCPU, 4 GB RAM and 40 GB disk to start. Put it where your data protection impact assessment
  requires (for example a UK data centre).
- A public IP address, and SSH access as a user with `sudo`.

**DNS**

- An `A` record for `qms.example.org` pointing at the VM's public IP address. Check it before you
  go on, because Let's Encrypt connects to that name:

  ```bash
  dig +short qms.example.org        # must print the VM's public IP address
  ```

**Network**

- Inbound: port **22** (SSH) and ports **80** and **443** from the internet. Port 80 is needed for
  the certificate challenge and for the redirect to HTTPS. Nothing else is opened.
- Port **8443** is for administration only and is reachable through an SSH tunnel, never from the
  internet (see [Administration](deployment.md#administration-admin-through-an-ssh-tunnel)).

**Accounts and details to have ready**

- An email address for Let's Encrypt. It receives expiry warnings, so use a mailbox someone reads.
- An SMTP relay for notification emails (host, port, user and password).
- An off-site backup destination, required for production: another server reachable over SSH, or a
  Google shared drive (see [Off-site backups](deployment.md#off-site-backups)).
- Your sign-in providers, if you use single sign-on (client ids and secrets).
- The container image for the release you are deploying, for example `ghcr.io/your-org/samd_qms:1.0.0`.
  If the image is private, a registry token that can read it.

**Your workstation**

- `git`, `make`, Python 3 and `ansible-core` (`pip install ansible-core`), and the repository:

  ```bash
  git clone https://github.com/your-org/eQMS.git && cd eQMS
  ```

---

## 2. Let's Encrypt: how the certificate is obtained and kept current

- The site proves it controls `qms.example.org` by answering a challenge on **port 80**. Apache
  serves the challenge from a shared folder that certbot writes to. Nothing else is needed.
- The first certificate is requested when the stack starts. Until it is issued, Apache serves a
  temporary self-signed certificate, so browsers show a warning. The warning goes away once
  Let's Encrypt issues the real certificate; check that with [section 5](#5-check-the-certificate).
- Certificates last 90 days. certbot tries to renew them every 12 hours and only renews when they
  are close to expiry. Apache checks each hour and reloads gracefully when a renewed certificate
  appears, without dropping connections.
- The certificate and its private key are kept in the Docker volume `samd_qms_letsencrypt`.

**Rate limits.** Let's Encrypt limits failed attempts. At the time of writing, a hostname may fail
validation only a few times an hour, and only a small number of certificates may be issued for the
same names in a week. So get the DNS right first, and do not repeat a failing deployment in a loop.
Current limits are on [letsencrypt.org](https://letsencrypt.org/docs/rate-limits/). The certbot
container retries once an hour if issuance fails, which stays inside those limits.

---

## 3. Ubuntu, Debian or Red Hat 9/10 (Ansible)

This section applies to Ubuntu 22.04 and 24.04, Debian 12, RHEL 9 and RHEL 10. The steps are the
same on all four. Rocky Linux and AlmaLinux: first do [section 6](#6-rocky-linux-almalinux-and-other-rebuilds-by-hand)
by hand, then follow this section and skip 3.2.

### 3.1 Describe the server

Copy the examples and set the server name, the image and the settings:

```bash
cd deploy/ansible
cp inventory.example.ini inventory.ini
```

Edit `inventory.ini` so the production host is the public name:

```ini
[production]
qms.example.org ansible_user=admin
```

`ansible_user` must be an account that already exists on the server and can use `sudo`. Do not
use `qmsdeploy`: provisioning creates that user.

Edit `group_vars/qms/vars.yml` (shared settings) and `group_vars/production/vars.yml` (production
only). The ones that matter for the certificate and the first start:

| Variable | Set to |
| --- | --- |
| `qms_image` | Your image, e.g. `ghcr.io/your-org/samd_qms` |
| `qms_version` | The release to run, e.g. `1.0.0` (you can also pass it on the command line) |
| `qms_domain` | `qms.example.org` (defaults to the inventory name) |
| `qms_url_prefix` | Empty for option A. For option B, put `"/qms"` in the host variables file (above); do not set it here, or every server inherits it |
| `qms_product_name` | The name shown in titles, headers, footers, emails and reports. Defaults to `SAMD_QMS`. Choose it before go-live. The validation records keep the name SAMD_QMS. |
| `acme_email` | The Let's Encrypt contact address (see section 1) |
| `admin_ssh_keys` | Public keys allowed to log in as the deploy user. Set at least one, or provisioning stops, so you cannot lock yourself out |
| `smtp_host` and the SMTP settings | Your relay |
| `backup_offsite_method` | `rsync` or `gdrive` (required for production) |
| `qms_sso_allowed_domains`, `qms_signer_sso_providers`, `qms_signer_email_domains` | Your organisation's sign-in and signer rules (required for production) |

Create the secrets file, fill it in and encrypt it:

```bash
cp vault.example.yml group_vars/qms/vault.yml
python3 -c "import secrets; print(secrets.token_urlsafe(48))"   # use for each secret
$EDITOR group_vars/qms/vault.yml
echo 'a long random passphrase' > ~/.samd_qms_vault_pass && chmod 600 ~/.samd_qms_vault_pass
ansible-vault encrypt group_vars/qms/vault.yml
cd ../..
```

Commit only the encrypted `vault.yml`, never the plain one, and keep a copy of the vault passphrase
somewhere safe. Without it, the encrypted backups cannot be decrypted.

### 3.2 Prepare the server

Rocky Linux and AlmaLinux: skip this step. You prepared the server in section 6.

```bash
make provision ENV=production
```

This installs Docker from Docker's own repository, creates the deploy user (SSH keys only), sets
up the directories, hardens SSH (no passwords, no root login, forwarding only to the admin tunnel),
enables the firewall (22, 80 and 443 only), fail2ban, automatic security updates and time sync, and
schedules the off-site backups.

Check that you can log in as the deploy user before you go on:

```bash
ssh qmsdeploy@qms.example.org 'docker --version && docker compose version'
```

### 3.3 Deploy a release

```bash
make deploy ENV=production VERSION=1.0.0
```

The playbook refuses placeholder secrets, an unpinned version, and production without off-site
backups and the signer rule. It then writes the configuration, pulls the image, backs up, applies
the database migrations, starts the containers, waits until the site answers over HTTPS, and
records the deployment. The first start also requests the certificate.

Continue at [section 4](#4-first-start).

---

## 4. First start

Create the first QMS administrator. This is the account people use to run SAMD_QMS. It asks for
the password at a prompt, so the password does not end up in the shell history:

```bash
scripts/remote.sh -e production manage create_qms_admin <username> --email <address>
```

Run it from your workstation, in the repository. Use `-e production` as well. `remote.sh` shows the
host name and asks you to type it before the command runs. Then sign in at the address you chose
in section 1 (`https://qms.example.org/` or `https://qms.example.org/qms/`). The first sign-in
asks you to set up an authenticator app, because two-factor sign-in is on in production.

Only if you also need Django's own administration site (`/admin/`, through the tunnel), create a
superuser on the server too. It is separate from the QMS administrator:

```bash
ssh qmsdeploy@qms.example.org
cd /opt/samd_qms
docker compose -f compose.prod.yaml exec app python manage.py createsuperuser
```

Then follow the in-app help for setting up devices, teams and roles.

### Single sign-on callbacks

If you use single sign-on, register the callback address with each provider, using the address you
chose in section 1. The callback must match exactly, or sign-in fails with a redirect error.

| Option | Callback to register, for each provider |
| --- | --- |
| A. Root of the name | `https://qms.example.org/accounts/<provider>/login/callback/` |
| B. Path | `https://qms.example.org/qms/accounts/<provider>/login/callback/` |

`<provider>` is `microsoft`, `google`, `github`, `orcid` or `linkedin`, for the ones you have
configured.

---

## 5. Check the certificate

Watch the certificate request:

```bash
ssh qmsdeploy@qms.example.org 'cd /opt/samd_qms && docker compose -f compose.prod.yaml logs certbot'
```

A successful issue ends with "Successfully received certificate". If the log shows errors, see
[Troubleshooting](#troubleshooting).

Check the certificate the public site serves (from your workstation):

```bash
echo | openssl s_client -connect qms.example.org:443 -servername qms.example.org 2>/dev/null \
  | openssl x509 -noout -issuer -subject -enddate
```

The issuer should name Let's Encrypt, and the subject should be `qms.example.org`. The browser
padlock should show a valid certificate with no warning.

Check that renewal works, without issuing a real certificate (certbot's dry run uses Let's Encrypt's
test service):

```bash
ssh qmsdeploy@qms.example.org 'cd /opt/samd_qms && docker compose -f compose.prod.yaml exec certbot certbot renew --dry-run'
```

---

## 6. Rocky Linux, AlmaLinux and other rebuilds (by hand)

Use this section only for Rocky Linux 9, AlmaLinux 9 and similar rebuilds. Ubuntu, Debian, RHEL 9
and RHEL 10 do not use it: `make provision` does these steps for them. Run the steps below as a
user with `sudo` on the server. They match what `provision.yml` does, so the result is the same as
[section 3.2](#32-prepare-the-server).

**Docker.** Use Docker's `centos` repository for Rocky Linux and AlmaLinux:

```bash
sudo dnf -y install dnf-plugins-core
sudo dnf config-manager --add-repo https://download.docker.com/linux/centos/docker-ce.repo
sudo dnf -y install docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin
```

Set the same log rotation and daemon options the playbook uses, in `/etc/docker/daemon.json`:

```json
{
  "log-driver": "json-file",
  "log-opts": { "max-size": "20m", "max-file": "10" },
  "live-restore": true,
  "no-new-privileges": true
}
```

Then start Docker:

```bash
sudo systemctl enable --now docker
```

**Deploy user.** Create the user, let it use Docker, and give it your SSH key. Replace the key with
your own public key:

```bash
sudo useradd --create-home qmsdeploy
sudo usermod -aG docker qmsdeploy
sudo install -d -m 700 -o qmsdeploy -g qmsdeploy /home/qmsdeploy/.ssh
echo 'ssh-ed25519 AAAA... you@workstation' | sudo tee /home/qmsdeploy/.ssh/authorized_keys >/dev/null
sudo chown qmsdeploy:qmsdeploy /home/qmsdeploy/.ssh/authorized_keys
sudo chmod 600 /home/qmsdeploy/.ssh/authorized_keys
sudo install -d -m 750 -o qmsdeploy -g qmsdeploy /opt/samd_qms
```

**SSH hardening.** Put the playbook's settings in a drop-in file, check it, then restart sshd:

```bash
sudo tee /etc/ssh/sshd_config.d/50-samd-qms.conf >/dev/null <<'EOF'
PasswordAuthentication no
KbdInteractiveAuthentication no
PermitRootLogin no
PubkeyAuthentication yes
MaxAuthTries 4
X11Forwarding no
AllowTcpForwarding local
PermitOpen 127.0.0.1:8443
AllowAgentForwarding no
AllowStreamLocalForwarding no
GatewayPorts no
PermitTunnel no
ClientAliveInterval 300
ClientAliveCountMax 2
EOF
sudo sshd -t && sudo systemctl restart sshd
```

Before you close your current session, open a second one and check that you can still log in.

**Firewall.** firewalld is the Red Hat firewall. Open SSH, HTTP and HTTPS only:

```bash
sudo firewall-cmd --permanent --add-service=ssh --add-service=http --add-service=https
sudo firewall-cmd --reload
```

**SELinux.** Keep it enforcing. The Compose file labels the bind mounts it needs (`:z`), so the
containers can read them. Check the mode with `getenforce`; it should print `Enforcing`.

**Updates and intrusion protection.** Install fail2ban and automatic security updates:

```bash
sudo dnf -y install fail2ban dnf-automatic
sudo systemctl enable --now fail2ban
sudo sed -i 's/^apply_updates = no/apply_updates = yes/' /etc/dnf/automatic.conf
sudo systemctl enable --now dnf-automatic.timer
```

**Time sync.** `sudo dnf -y install chrony && sudo systemctl enable --now chronyd`.

Then continue from your workstation with [section 3.1](#31-describe-the-server) and
[section 3.3](#33-deploy-a-release). Skip 3.2, since you have just done its work by hand. Two
settings in 3.1 matter here: `ansible_user` must be the sudo account you created or already use
(not `qmsdeploy`), and `admin_ssh_keys` must list the keys that should keep access.

> **Note.** RHEL 9 and RHEL 10 do not use this section. Follow [section 3](#3-ubuntu-debian-or-red-hat-910-ansible).

---

## 7. Keeping it running

To change the software and release it, see [Developing and releasing](developing-and-releasing.md).


| Task | How |
| --- | --- |
| See the containers | `ssh qmsdeploy@qms.example.org 'cd /opt/samd_qms && docker compose -f compose.prod.yaml ps'` |
| Follow the logs | `scripts/remote.sh -e production logs web` (or `app`, `certbot`, `scheduler`, `db`) |
| Upgrade to a new release | `make deploy ENV=production VERSION=1.0.1` (backs up first) |
| Roll back | `make deploy ENV=production VERSION=1.0.0`. If the new release ran migrations, restore the pre-deploy backup first (see [deployment.md](deployment.md#backups-and-restore)) |
| Administer the site | `scripts/remote.sh -e production tunnel` (prints the address), then open `https://localhost:8443/admin/` (or `/qms/admin/` for option B) |
| Check the certificate | [Section 5](#5-check-the-certificate) |
| Check the health of the site | `curl -s https://qms.example.org/healthz` (option B: `https://qms.example.org/qms/healthz`), or `scripts/remote.sh -e production health` |

The certificate renews without action. Check the expiry date now and then with section 5, and
investigate if certbot reports failures for more than a day.

---

## Troubleshooting

| Symptom | Likely cause and fix |
| --- | --- |
| Browser shows a self-signed certificate warning | Let's Encrypt has not issued yet. Read the certbot log (below). |
| certbot log says the challenge failed or timed out | DNS does not point at this server (check `dig +short`), or port 80 is blocked by a firewall or cloud security group. Fix it; certbot retries each hour. |
| certbot log says too many failed authorizations or certificates | You have hit a Let's Encrypt rate limit. Wait for the limit to reset (the error gives the time); the next retry then succeeds. |
| certbot log says the email address is invalid | `acme_email` is not a real mailbox. Correct it and redeploy. |
| Site works over HTTP but not HTTPS | Port 443 is blocked, or the web container is not running: check `docker compose ... ps` and `logs web`. |
| On Red Hat, the web container cannot read its files | SELinux is blocking them. Confirm the Compose file has `:z` on the `./apache` mounts, and that the files are in `/opt/samd_qms`. |
| `make deploy` says a secret is a placeholder | Set the value in `group_vars/qms/vault.yml`, then encrypt it again. |
| Option B: the root address does not redirect to `/qms/` | Check `qms_url_prefix` in `host_vars/<name>.yml` and redeploy. The redirect is written when the web container starts. |
| Option B: a page or the health check is 404 | The address is missing `/qms`. Use `/qms/` for pages and `/qms/healthz` for the health check. |
| Sign-in with single sign-on fails with a redirect or callback error | The callback registered with the provider does not match section 4, character for character (option A has no `/qms`; option B has it). |

To read the certificate-related logs:

```bash
ssh qmsdeploy@qms.example.org 'cd /opt/samd_qms && docker compose -f compose.prod.yaml logs --tail=100 certbot web'
```
