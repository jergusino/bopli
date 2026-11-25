# Bopli waitlist

Single-page landing with a waitlist signup.

- `index.html`: the page, hosted on GitHub Pages.
- `worker/`: Cloudflare Worker (`bopli-waitlist`) with a D1 database (`bopli-waitlist`). The page POSTs `{email}` to `/join`; the Worker validates it and stores it in the `signups` table. Only requests from `https://jergusino.github.io` are accepted.

## See the signups

Cloudflare dashboard → Storage & databases → D1 → `bopli-waitlist` → Console:

```sql
SELECT email, created_at FROM signups ORDER BY id;
```

## Deploy changes to the Worker

```sh
cd worker
npx wrangler deploy
```

Schema lives in `worker/schema.sql` (`npx wrangler d1 execute bopli-waitlist --remote --file=schema.sql`).
