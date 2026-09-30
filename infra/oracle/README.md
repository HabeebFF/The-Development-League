# Hosting on Oracle Cloud's free server

The whole site (database, API, worker, website and HTTPS) runs on one Oracle Cloud
"Always Free" Ampere VM with Docker Compose. It costs nothing while it stays within the
free limits (up to 4 CPUs and 24 GB memory for Ampere VMs).

## 1. Create the server (Oracle console)

1. Compute > Instances > Create instance.
   - Image: **Ubuntu 24.04**. Shape: **VM.Standard.A1.Flex**, 4 OCPUs and 24 GB
     (2 and 12 is plenty if 4 is "out of capacity").
   - SSH keys: *Generate a key pair* and download the private key.
2. Open the web ports: Networking > Virtual cloud networks > the VCN > the subnet >
   Default security list > Add ingress rules: source `0.0.0.0/0`, TCP, destination
   ports `80,443`.
3. Note the instance's public IP. Without a domain, the site's address can be
   `<ip with dashes>.sslip.io` (for 203.0.113.7: `203-0-113-7.sslip.io`), which points
   at the IP for free.

Billing > Budgets: a $1 alert is a good safety net.

## 2. Install the site

From a computer with the repo and the key (Windows PowerShell works):

```bash
ssh -i oracle-tdl.key ubuntu@<ip>                     # check the key works, then exit
git archive -o tdl.tar HEAD                           # the current code
scp -i oracle-tdl.key tdl.tar ubuntu@<ip>:
ssh -i oracle-tdl.key ubuntu@<ip> "mkdir -p tdl && tar -xf tdl.tar -C tdl && bash tdl/infra/oracle/setup.sh <domain>"
```

`setup.sh` installs Docker, opens ports 80 and 443 in the server's firewall, writes
`.env` with fresh secrets (kept on the server only) and starts everything. Caddy gets
the HTTPS certificate by itself within a minute.

Then create the first admin account:

```bash
ssh -i oracle-tdl.key ubuntu@<ip>
cd tdl && sudo docker compose --env-file .env -f infra/docker-compose.prod.yml exec web python manage.py createsuperuser
```

## Updating

Copy the new code the same way, then run `bash tdl/infra/oracle/setup.sh` again. The
database, uploads and `.env` are kept.

## Moving data from a local install

To bring matches and accounts from the local Docker install on a PC:

```bash
# On the PC, in the repo folder
docker compose -f infra/docker-compose.yml exec db pg_dump -U tdl -Fc -f /tmp/tdl.dump tdl
docker compose -f infra/docker-compose.yml cp db:/tmp/tdl.dump tdl.dump
docker compose -f infra/docker-compose.yml cp web:/data/media media
tar -cf media.tar media
scp -i oracle-tdl.key tdl.dump media.tar ubuntu@<ip>:

# On the server, in ~/tdl
C="sudo docker compose --env-file .env -f infra/docker-compose.prod.yml"
$C cp ~/tdl.dump db:/tmp/tdl.dump
$C exec db pg_restore -U tdl -d tdl --clean --if-exists --no-owner /tmp/tdl.dump
tar -xf ~/media.tar -C ~ && $C cp ~/media/. web:/data/media/
$C exec -u root web chown -R app /data/media
$C restart web worker
```

## Good to know

- Emails are only printed to the logs (`$C logs web`) until an email sender is set in
  `.env`. Managers can copy invite links from the Members page and send them on WhatsApp.
- Uploaded match files and map images live in Docker volumes on the server's disk
  (`USE_S3=false`). Only map images and team logos are served publicly.
- Oracle can stop free VMs it considers idle (very low CPU, network and memory use over
  7 days). A quiet site can look idle. Upgrading the account to Pay As You Go removes
  that rule, and the Always Free resources stay free.
