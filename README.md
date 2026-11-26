# Bopli waitlist

Single-page landing with a waitlist signup.

- `index.html`: the page, hosted on GitHub Pages (custom domain via `CNAME`).
- `worker/`: Cloudflare Worker (`klucenka-waitlist`) with a D1 database (`klucenka-waitlist`). The page POSTs `{email}` to `/join`; the Worker validates it and stores it in the `signups` table. Only requests from `https://bopli.jergusino.com` (and the old `https://jergusino.github.io`) are accepted. Live at https://bopli.jergusino.com.

## See the signups

Cloudflare dashboard → Storage & databases → D1 → `klucenka-waitlist` → Console:

```sql
SELECT email, created_at FROM signups ORDER BY id;
```

## Deploy changes to the Worker

```sh
cd worker
npx wrangler deploy
```

Schema lives in `worker/schema.sql` (`npx wrangler d1 execute klucenka-waitlist --remote --file=schema.sql`).
