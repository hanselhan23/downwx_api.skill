# down.mptext.top API Notes

Base URL:

```text
https://down.mptext.top
```

Authentication:

- Send `X-Auth-Key: <key>` on API requests, or
- Send a cookie named `auth-key`.

Login/key relationship:

- The website login and API key use the same session system.
- Scanning to log in on down.mptext.top refreshes the API key.
- Each successful website login may rotate the API key; after any login, re-read and persist the latest key.
- When the website login expires, the API key expires too.

Operational guidance:

- Prefer `--check` or `--remind` for normal health checks; they do not open the website login flow.
- Use `--refresh` only after the current key is invalid or when the operator intentionally wants a new key.
- Use a persistent browser profile so the website session can be reused and manual QR scanning is needed less often.

Validation endpoint:

```http
GET /api/public/v1/authkey
```

Success indicators:

- `{"code": 0, ...}`
- or `{"base_resp": {"ret": 0, ...}, ...}`

Failure indicators:

- `{"code": -1, ...}`
- or `{"base_resp": {"ret": -1, ...}, ...}`

The site may expose the refreshed key in a cookie, page storage, or the auth-key endpoint response. Prefer a candidate only after validating it through `/api/public/v1/authkey`.
