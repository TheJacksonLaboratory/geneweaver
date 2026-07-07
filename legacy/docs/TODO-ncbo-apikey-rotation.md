# TODO: Remove the hardcoded NCBO API key & rotate it

**Status:** OPEN — key must be provisioned as a secret, then rotated
**Severity:** Medium (embedded credential; low blast radius — a free BioPortal annotator key)
**Filed:** 2026-07-07
**Refs:** G3-770, GWC-8, PR #2 (Copilot review), umbrella G3-769; sibling of Auth0 rotation G3-761

## What

`legacy/src/annotator.py` embeds a real NCBO BioPortal annotator API key as the
fallback for the `GW_NCBO_API_KEY` environment variable:

```python
API_KEY = os.environ.get('GW_NCBO_API_KEY', '2709bdd2-...')  # usable key in source
```

The key predates this work (it was previously an unconditional hardcoded
literal) and is therefore already in git history. During the GWC-8 fix the
endpoint/key were made env-driven and the endpoint switched to **https** (so the
`apikey` query param is no longer sent in cleartext), but the usable fallback
value is still shipped in the repo. Flagged by Copilot on PR #2.

## Why it wasn't removed immediately

Defaulting `API_KEY` to empty would re-break annotation on dev (just restored
under GWC-8) until `GW_NCBO_API_KEY` is provisioned in the cluster. So the
fallback is intentionally retained until the secret exists — annotation keeps
working and the key is already env-overridable.

## Checklist

- [ ] Provision `GW_NCBO_API_KEY` as a **k8s Secret** referenced by the legacy
      deployment env (dev via the monorepo; sqa/stage/prod via the standalone
      repos). Confirm the wiring:
      ```
      kubectl get deploy geneweaver-legacy -n dev -o yaml | grep -iA3 -E 'env|secretRef|configMapRef'
      ```
- [ ] Change `annotator.py` to default `API_KEY` to empty (require the env var)
      once the secret is in place.
- [ ] **Rotate** the exposed key: register/regenerate at
      https://bioportal.bioontology.org/accounts and revoke the old value; set
      the new value in the Secret. (The key value is intentionally not repeated
      here — see git history / the Secret store.)
- [ ] Verify annotation still works: in the web pod,
      `annotator.annotate_text(...)` returns > 0, and a real upload produces
      `Description, NCBO Annotator` rows in `extsrc.geneset_ontology`.

## Prevention

Do not embed API keys in source. Read them from the environment / a secret
store, and never log the value (see the CLAUDE.md secrets guardrail).
