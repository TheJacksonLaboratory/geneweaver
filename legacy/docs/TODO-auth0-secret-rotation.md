# TODO: Rotate the legacy Auth0 client secret (exposed in logs)

**Status:** OPEN — secret must be rotated
**Severity:** High (credential exposure)
**Filed:** 2026-06-29

## What happened

`legacy/src/application.py` logged the full Auth0 configuration — **including the
`client_secret` in plaintext** — at `CRITICAL` level on every app startup:

```python
logging.critical('Auth0 client_secret: ' + config.get('auth', 'client_secret'))
```

Those debug lines have now been removed (commit on branch
`G3-748-finish-migration-of-geneweaver-to-monorepo`), which stops **future**
leakage. It does **not** undo the exposure that already happened.

## Why rotation is still required

The secret was written to the running pod's stdout and therefore into
**Cloud Logging** for the dev cluster (`jax-cluster-dev-10`, namespace `dev`),
where it is readable by anyone with log-view access. Any credential that has
been logged in plaintext must be considered compromised and rotated.

- Auth0 tenant: `thejacksonlaboratory.auth0.com`
- Affected application: the **legacy GeneWeaver** Auth0 app
  (client_id `x9IiBRyt8lS3lsqrz2H6aO1leRBbxyb7` — note this is a *different*
  app from the API, whose client_id is `aE6dpT04mGlvPeUXl4RYGSnCjvHEuawd`)
- The secret value itself is intentionally **not** recorded here. See the
  pre-fix pod logs / the secret store if you need to confirm which value to revoke.

## Rotation checklist

- [ ] In the Auth0 dashboard → Applications → the legacy GeneWeaver app →
      Settings → **Rotate the client secret** (generates a new value, invalidates the old).
- [ ] Update the secret everywhere it is consumed:
  - [ ] **In-cluster (dev):** locate the source backing the legacy deployment's
        `auth.client_secret` and update it. Confirm the source with:
        ```
        kubectl get deploy geneweaver-legacy -n dev -o yaml | grep -iA3 -E 'env|secretRef|configMapRef|volume'
        ```
        then update the referenced Secret/ConfigMap (and repeat for `sqa`,
        `stage`, `prod` namespaces if they share the same Auth0 app).
  - [ ] **Local dev:** `legacy/src/.env` → `AUTH_CLIENTSECRET=` (untracked file).
  - [ ] Any other deployment/config that injects `AUTH_CLIENTSECRET` /
        `auth.client_secret`.
- [ ] Restart the legacy deployment(s) so the new secret is picked up:
      `kubectl rollout restart deploy/geneweaver-legacy -n dev`
- [ ] Verify login still works end-to-end through `https://geneweaver-dev.jax.org/`
      (302 → Auth0 → callback → authenticated).
- [ ] (Cloud Logging hygiene) Consider purging / restricting access to the
      historical dev log entries that contain the old secret.

## Prevention

- The plaintext logging has been removed. If Auth0 config ever needs to be
  logged for debugging, log only non-secret fields (client_id, domain,
  endpoints) and never the secret.
