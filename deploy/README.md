# Running Loose Ends 24/7 on AWS

The agent only exists while its process is alive. On a laptop that means it dies when you
close the lid — and a judge who opens the App Home to a dead tab sees nothing. This puts it
on a box that stays up.

**EC2, not Lambda.** Socket Mode holds a long-lived WebSocket; Lambda has no persistent
execution model and simply cannot host this. Fargate would work but needs EFS to persist one
SQLite file — a lot of moving parts for no gain. A `t4g.micro` with an EBS disk and systemd
is the honest right answer: **~$6/month**, and it guarantees the single instance this app
requires.

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

`.env` is deliberately not in the repo. Create it on the instance:

```bash
sudo mkdir -p /opt/looseends
sudo nano /opt/looseends/.env       # paste your local .env contents
sudo chmod 600 /opt/looseends/.env
```

It needs at least `SLACK_BOT_TOKEN`, `SLACK_APP_TOKEN`, `SLACK_SIGNING_SECRET`, and
`DGRID_API_KEY`. Add `SLACK_USER_TOKEN` for Real-Time Search and `DEMO_CHANNEL` for the seed
script.

## 3. Bootstrap

```bash
curl -fsSL https://raw.githubusercontent.com/zaxcoraider/loose-ends/main/deploy/bootstrap.sh \
  | sudo bash
```

Installs Python, clones the repo, builds the venv, and starts both services under systemd.
Re-run it any time to deploy the latest `main`.

## 4. Verify

```bash
systemctl status looseends-app looseends-mcp
journalctl -u looseends-app -f
```

You want to see:

```
⚡ Loose Ends running
🔎 Real-Time Search: enabled (user token present)
scheduler started (every 2.0 min)
Bolt app is running!
```

Then say something in Slack you'd regret forgetting, and watch for the 👀.

---

## Things that will bite you

**Run ONE instance.** Two Socket Mode connections split events between them: half your
nudges vanish, buttons fire twice. Never put this behind an autoscaling group, and **stop
the app on your laptop before starting it here** — same failure.

**Stop the local copy first.** The most likely cause of a weird demo is your laptop and the
server both connected.

**EBS survives reboot and stop/start, not termination.** The SQLite file lives on the root
volume. Terminating the instance destroys your tracked loose ends. Snapshot the volume if
they ever matter.

**Redeploy = restart = a dropped WebSocket for a second.** Harmless; Bolt reconnects.

```bash
# deploy latest main
curl -fsSL https://raw.githubusercontent.com/zaxcoraider/loose-ends/main/deploy/bootstrap.sh | sudo bash

# reset to a clean demo state (from the box)
sudo -u looseends /opt/looseends/.venv/bin/python /opt/looseends/scripts/seed_demo.py
```

## Cost

`t4g.micro` on-demand is about **$6/month**, plus pennies for the 8 GB volume. A $100 credit
runs this for well over a year. Set a **billing alarm** anyway — that is the one thing that
turns a free demo into a surprise.
