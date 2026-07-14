# Running Loose Ends 24/7 on AWS

The agent only exists while its process is alive. On a laptop that means it dies when you
close the lid — and a judge who opens the App Home to a dead tab sees nothing. This puts it
on a box that stays up.

**Both workspaces, one box.** The original workspace and the judging mirror are two Slack
apps with two bot tokens, so each needs its own process. They run as two instances of one
systemd *template* unit, sharing a single MCP ticket server:

```
looseends-mcp                 127.0.0.1:8765, shared, holds no credentials
├── looseends-app@judging     env/judging.env   → the judging mirror
└── looseends-app@looseend    env/looseend.env  → the original workspace
```

**EC2, not Lambda.** Socket Mode holds a long-lived WebSocket; Lambda has no persistent
execution model and simply cannot host this. Fargate would work but needs EFS to persist the
SQLite files — a lot of moving parts for no gain. A `t4g.micro` with an EBS disk and systemd
is the honest right answer: **~$6/month for both agents**, and it guarantees exactly one
process per workspace, which is the thing this app actually requires.

**Nothing listens on the internet.** Socket Mode is outbound-only and the MCP server binds
`127.0.0.1`. The instance needs **zero inbound ports** — no load balancer, no public
endpoint, no TLS certificate. Use SSM Session Manager for shell access and the security
group can deny all inbound traffic.

---

## 1. Launch the instance

Console → EC2 → Launch instance:

| Setting | Value |
|---|---|
| AMI | **Amazon Linux 2023** (ARM64) |
| Type | **t4g.micro** |
| Key pair | *Proceed without a key pair* (use SSM instead) |
| Network | default VPC, public subnet, **auto-assign public IP: enable** |
| Security group | **no inbound rules at all**; leave outbound open |
| IAM role | one with **`AmazonSSMManagedInstanceCore`** attached |
| Storage | 8 GB gp3 (default) |

> The public IP is only for *outbound* internet (Slack + the LLM gateway). Nothing can
> connect *in*. If you prefer, drop the public IP and use a NAT gateway — but that costs
> more than the instance does.

Connect with **EC2 → Connect → Session Manager**. No SSH key, no open port 22.

## 2. Put the secrets on the box

Env files are deliberately not in the repo. **One file per workspace**, named for the
instance that will serve it — the filename *is* the systemd instance name:

```bash
sudo mkdir -p /opt/looseends/env

sudo nano /opt/looseends/env/judging.env    # paste your local .env
sudo nano /opt/looseends/env/looseend.env   # paste your local .env.looseend

sudo chmod 700 /opt/looseends/env
sudo chmod 600 /opt/looseends/env/*.env
```

Each file needs its own `SLACK_BOT_TOKEN`, `SLACK_APP_TOKEN`, `SLACK_SIGNING_SECRET`, and
`DGRID_API_KEY` (the gateway key can be the same one), plus `SLACK_USER_TOKEN` for Real-Time
Search and `DEMO_CHANNEL` for the seed script.

> **Give each file a distinct `LOOSEENDS_DB`** (`loose_ends_judging.sqlite` and
> `loose_ends.sqlite`). Miss this and both workspaces write their loose ends into one
> database — every dashboard then shows the other workspace's items, with permalinks a judge
> cannot open. Your local env files already set this correctly; copy them as they are.

Want only one workspace live? Put only that one env file in `env/`.

## 3. Bootstrap

```bash
curl -fsSL https://raw.githubusercontent.com/zaxcoraider/loose-ends/main/deploy/bootstrap.sh \
  | sudo bash
```

Installs Python, clones the repo, builds the venv, then starts the MCP server plus **one app
service per env file it finds**. Re-run it any time to deploy the latest `main`. If the box
was set up before multi-workspace support, it migrates the old `/opt/looseends/.env` to
`env/judging.env` and retires the old single-workspace unit.

## 4. Verify

```bash
systemctl status looseends-mcp looseends-app@judging looseends-app@looseend
journalctl -u looseends-app@judging -f
```

Each app should say:

```
⚡ Loose Ends running
🔎 Real-Time Search: enabled (user token present)
scheduler started (every 2.0 min)
Bolt app is running!
```

Then say something in **each** workspace that you'd regret forgetting, and watch for the 👀.
A 👀 in one workspace proves nothing about the other — they are separate processes.

---

## Things that will bite you

**One process per workspace — but never two per workspace.** Two Socket Mode connections on
the same bot token split events between them: half your nudges vanish and buttons fire twice.
systemd guarantees one per instance name. **Stop the copy on your laptop before starting the
box** — a laptop and a server on the same token is exactly this failure, and it is the most
likely cause of a weird demo.

**The two agents are independent.** Separate processes, separate SQLite files, separate
schedulers. `systemctl restart looseends-app@judging` does not touch the original workspace.

**EBS survives reboot and stop/start, not termination.** The SQLite files live on the root
volume. Terminating the instance destroys your tracked loose ends. Snapshot the volume if
they ever matter.

**Redeploy = restart = a dropped WebSocket for a second.** Harmless; Bolt reconnects.

```bash
# deploy latest main (restarts every workspace)
curl -fsSL https://raw.githubusercontent.com/zaxcoraider/loose-ends/main/deploy/bootstrap.sh | sudo bash

# restart just one workspace
sudo systemctl restart looseends-app@judging

# reset a workspace to a clean demo state. ENV_FILE picks which one; the cd matters,
# because LOOSEENDS_DB is a relative path and would otherwise seed a stray database.
cd /opt/looseends && sudo -u looseends ENV_FILE=env/judging.env \
  .venv/bin/python scripts/seed_demo.py

# stop serving a workspace for good
sudo systemctl disable --now looseends-app@looseend
```

## Cost

`t4g.micro` on-demand is about **$6/month**, plus pennies for the 8 GB volume — and that is
for *both* agents, since the second process costs nothing but memory. A $100 credit runs this
for well over a year. Set a **billing alarm** anyway: that is the one thing that turns a free
demo into a surprise.
