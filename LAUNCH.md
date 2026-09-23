# Launch runbook (GitHub Education Pack path)

Everything in the code is done and tested locally. The remaining steps need accounts in your name, which I can't create for you (my rules bar me from creating accounts or handling passwords). Each step is a few clicks, and everything after account creation is automated by a script in this repo. Total time: about an hour. Running cost: **$0 for 12 months** on the student offers, then roughly $10/month.

Brand: **First Dig**. Checked 2026-09-23: zero hits in any field of the Canadian Trademarks Database, no company or product by that name, `firstdig.ca`, `.app`, `.io` unregistered (`.com` is on the aftermarket), `@firstdig` free on X and LinkedIn. Full research and the rejected alternatives are in NAME.md.

## 0. Verify the Education Pack (5 min)

education.github.com/pack → "Get your pack". You need your school email or proof of enrolment. Approval is usually instant to 3 days. Everything below assumes it's approved.

## 1. Push the code to GitHub (5 min)

Create an empty repo at github.com/new named `firstdig` (public is simplest for the server install; private works with a deploy token). Then:

```bash
cd ~/Developer/firstdig
git remote add origin https://github.com/YOUR_GITHUB_USER/firstdig.git
git push -u origin main
```

## 2. Domain: Name.com, free for a year (10 min)

1. education.github.com/pack/offers → find **Name.com** → "Get access" (it links you into name.com with the promo attached).
2. Search **firstdig** and pick **.app** (Google-run, HTTPS-only, clean, on the free list). If `.app` isn't shown as free, `.live` or `.dev` are the next choices.
3. Check out; the code applies itself. Turn **auto-renew off** on the domain so you're not charged next year without deciding.
4. Later, when there's revenue, buy `firstdig.com` and `firstdig.ca` (about $12 each per year) and point them at the same server. Not needed to launch.

Second free domain if you want it: Namecheap gives Pack members a free **.me** (nc.me). `firstdig.me` is available. Optional.

Also buy **firstdig.ca** the same day at Name.com or Namecheap (about $12/yr, not part of the pack): trades in Toronto trust a .ca, and it stops a squatter taking it once the site is public. Point it at the same server.

## 3. Server: Azure for Students, free for a year (15 min)

DigitalOcean left the Pack on Aug 1 2026, so Azure is the free path. Azure for Students gives $100 credit plus 750 free hours a month of a B1s VM for 12 months, no credit card, age 18+.

1. azure.microsoft.com/free/students → sign in with the same email → verify with your school.
2. Portal → **Create a resource → Virtual machine**:
   - Image: **Ubuntu Server 24.04 LTS**
   - Size: **Standard_B1s** (shows as "free services eligible")
   - Authentication: SSH public key (let it generate one and download it)
   - Inbound ports: **HTTP (80), HTTPS (443), SSH (22)**
   - **Advanced tab → Custom data**: paste the contents of `deploy/cloud-init.yaml` after replacing `YOUR_GITHUB_USER`, `YOUR_REPO` (firstdig) and `YOUR_DOMAIN` (firstdig.app).
3. Create. Note the **public IP** on the VM overview page. The install runs on its own for about 5 minutes (log: `/var/log/signals-install.log` on the VM).

Anything else with Ubuntu + a persistent disk works the same way (Hetzner CX22 is about $4/month if you'd rather pay than use Azure).

## 4. DNS (2 min)

At Name.com → your domain → DNS records: add an **A record**, host `@`, pointing at the VM's public IP, and a second A record for host `www`. Within a few minutes Caddy on the server fetches a certificate and https://firstdig.app is live. Check it from your laptop with `tests/smoke.sh https://firstdig.app`.

## 5. Email: Resend, free tier (10 min)

1. resend.com → sign up → **API Keys** → create one (full access).
2. On your laptop:
   ```bash
   cd ~/Developer/firstdig
   RESEND_API_KEY=re_xxx python3 scripts/resend_setup.py firstdig.app
   ```
   It registers the domain and prints the DNS records (SPF, DKIM, MX). Add them at Name.com, then re-run the script; when it prints `verified`, sign-in links and digests go out for real.

## 6. Configure the server (5 min)

SSH in (`ssh azureuser@<ip>` with the key you downloaded) and run:

```bash
sudo /opt/signals/deploy/configure.sh
```

It asks for your admin email, the public URL, the Resend key and the from-address, writes them into `/opt/signals/.env`, and restarts the app. Then sign in at https://firstdig.app/login with your admin email; the link arrives by email.

## 7. Payments: Stripe (20 min, can wait until the first customer)

1. stripe.com → sign up → complete the business profile (sole proprietor under your own name is fine; you'll need your SIN for tax reporting).
2. Developers → API keys → copy the **secret key**. Use the **test** key first.
3. Re-run `sudo /opt/signals/deploy/configure.sh` and paste it when asked. The script calls Stripe and creates the three CAD monthly prices ($79 / $99 / $149), the webhook endpoint, and stores the IDs and signing secret. Nothing to click in the Stripe dashboard.
4. Settings → Billing → Customer portal → turn it on (lets subscribers cancel themselves).
5. Test a checkout with card `4242 4242 4242 4242`, then repeat step 3 with the live key.

Until this step, Subscribe buttons say billing isn't switched on and free trials keep working.

## 8. Before the first outreach email

- Set `hello@example.com` in `app/web/templates/base.html` to a real address.
- Read `/terms` once.
- HST: not required until you pass $30,000 revenue in four consecutive quarters.

## 9. First 30 prospects

Teardown Feed: Google Maps "pool builder Toronto", "landscaping Leaside", "fence company Toronto", "custom closets Toronto", "window and door company Toronto". Opening Soon: "POS systems Toronto", "restaurant insurance broker Toronto", "commercial cleaning Toronto", "restaurant supply Toronto", "commercial signage Toronto".

Email template:

> Subject: 5 Stratheden Rd just filed a $2.5M teardown
>
> Hi —, I run a small feed that reads Toronto's permit filings every morning and flags the teardowns, new houses and big additions in your area. Last week in Leaside, Lawrence Park and Moore Park that was 5 new houses, 6 demolitions and 2 garden suites, with the builder's name on each. Here's the public version: https://firstdig.app/app/teardown?hoods=Leaside-Bennington,Lawrence%20Park%20South,Rosedale-Moore%20Park. Subscribers see filings the morning after they land. Two weeks free, no card, if you want to see whether it pays for itself. — Jason

## 10. Keep an eye on

- https://firstdig.app/admin → Pipeline runs. Two failures in a row means the City changed a file; the note says which.
- The maps use OpenStreetMap's public tiles. Fine at small scale; when there are paying customers, get a free MapTiler key and swap the tile URL in `app/web/static/app.js` (two places).
- Azure free hours reset monthly; B1s at 24/7 is 720–744 hours, under the 750 cap. After 12 months the VM costs about $9/month, or move to Hetzner.
- Updating the app after you change code: `git push`, then on the server `sudo /opt/signals/deploy/install.sh` (it pulls and restarts).
