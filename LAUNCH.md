# Launch checklist

Everything in the codebase is done. What's left needs accounts in your name, which I can't create for you. Budget about 90 minutes. Total running cost is roughly $8 to $15 a month until you have customers.

## 1. Domain (10 min)

Buy a domain. Suggestions to check: `torontosignals.ca`, `teardownfeed.com`, `openingsoon.ca`. Namecheap or Cloudflare Registrar are fine. You'll point it at the host in step 3.

## 2. Email sending: Resend (10 min)

1. Sign up at resend.com (free tier: 3,000 emails/month, plenty).
2. Add your domain and put the DNS records they give you into your registrar.
3. Create an API key. Keep it for step 3.
4. Set `EMAIL_FROM="Toronto Signals <hello@yourdomain.ca>"`.

Until this is done the app still works: sign-in links show on screen in dev mode and digests are written to the log.

## 3. Hosting: Fly.io (20 min)

1. Install flyctl (`brew install flyctl` or the script on fly.io), `fly auth signup`.
2. In this folder:
   ```bash
   fly launch --copy-config --no-deploy      # accept the app name or choose one; region yyz (Toronto)
   fly volumes create data --size 3 --region yyz
   ```
3. Set secrets (generate the two random strings with `openssl rand -hex 32`):
   ```bash
   fly secrets set \
     SECRET_KEY=<random> \
     CRON_SECRET=<random> \
     ADMIN_EMAILS=you@example.com \
     BASE_URL=https://yourdomain.ca \
     RESEND_API_KEY=<from step 2> \
     EMAIL_FROM="Toronto Signals <hello@yourdomain.ca>"
   ```
4. `fly deploy`. First boot downloads the data and builds the index (2 to 3 minutes). Watch with `fly logs`.
5. `fly certs add yourdomain.ca` and add the CNAME/A records it prints to your registrar.
6. Open the site, sign in with your admin email, check `/admin`.

The Dockerfile sets `ENABLE_SCHEDULER=1`, so the machine refreshes data and sends digests every morning after 6:00 Toronto time on its own. Keep `min_machines_running = 1` in `fly.toml` so it never sleeps through that.

Alternative hosts that work with the same Dockerfile: Railway (add a volume at `/data`), Render (persistent disk at `/data`). Don't use a host without persistent disk; the SQLite file is the product.

## 4. Payments: Stripe (30 min)

1. Sign up at stripe.com, complete the business profile (you can operate as a sole proprietor under your own name).
2. Products → create three recurring monthly prices in CAD:
   - Teardown Feed, $79/month
   - Opening Soon, $99/month
   - Both feeds, $149/month
   Copy the three `price_...` IDs.
3. Developers → Webhooks → add endpoint `https://yourdomain.ca/billing/webhook` with events `checkout.session.completed`, `customer.subscription.created`, `customer.subscription.updated`, `customer.subscription.deleted`. Copy the signing secret.
4. Settings → Billing → Customer portal: enable it so subscribers can cancel and update cards themselves.
5. Settings → Tax: turn on automatic tax if you want Stripe to add HST, otherwise add 13% to the prices.
6. Set the secrets:
   ```bash
   fly secrets set STRIPE_SECRET_KEY=sk_live_... STRIPE_WEBHOOK_SECRET=whsec_... \
     STRIPE_PRICE_TEARDOWN=price_... STRIPE_PRICE_OPENINGS=price_... STRIPE_PRICE_BUNDLE=price_...
   ```
7. Test with a Stripe test card in test mode first (use `sk_test_` keys and test price IDs), then switch to live.

Until this is done the Subscribe buttons say billing isn't switched on and trials keep working. You can also just extend someone's trial by hand in SQLite if you want to invoice manually at first.

## 5. Before the first customer

- Change `hello@example.com` in `app/web/templates/base.html` to your real contact address.
- Read `/terms` once and make sure you're happy to stand behind it.
- Register for an HST number once you pass $30,000 in revenue in four consecutive quarters (CRA rule); before that you don't have to charge HST.
- Pick your first 30 prospects. For Teardown Feed: search Google Maps for "pool builder Toronto", "landscaping Leaside", "fence company Toronto", "custom closets Toronto". For Opening Soon: "POS systems Toronto", "restaurant insurance broker Toronto", "commercial cleaning Toronto", "restaurant supply Toronto".

## 6. The first email (copy this)

Subject: 5 Stratheden Rd just filed a $2.5M teardown

Hi —, I run a small feed that reads Toronto's permit filings every morning and flags the teardowns, new houses and big additions in your area. Last week in Leaside, Lawrence Park and Moore Park that was 5 new houses, 6 demolitions and 2 garden suites, with the builder's name on each. Here's the public version: [link to /app/teardown filtered to their neighbourhoods]. Subscribers see filings the morning after they land. Two weeks free, no card, if you want to see whether it pays for itself. — Jason

## 7. Map tiles

The maps use OpenStreetMap's public tile server, which is fine for a small site but is not meant for heavy commercial use. When you have paying customers, sign up for a free MapTiler or Stadia Maps key and swap the tile URL in `app/web/static/app.js` (two places). Ten minutes.

## 8. Watch these

- `/admin` → Pipeline runs. If a run fails two days running, the City changed a file; the error text says which.
- The AGCO file occasionally goes empty for a day. The pipeline keeps the old copy when a download is under 1 KB.
- Fly volume: 3 GB is fine for a year. `fly volumes list` shows usage.
