# AfriMentor AI — API Contracts (card O1.4)

OpenAPI 3.1 contract per microservice. Contracts are **generated** for consistency; edit
the generator, not the YAML by hand.

## Files

- `<service>.yaml` — one OpenAPI 3.1 spec per service (13 total).
- `index.html` — zero-build docs site (Redoc standalone) with a service picker.
- `../../redocly.yaml` — Redocly multi-API config for linting and building.
- `../../scripts/gen_openapi.py` — the generator.

`api-gateway.yaml` and `auth-user-service.yaml` reflect the **implemented** v1 endpoints
(card O1.3). The other 11 list their v1 endpoints with `TODO` bodies to be finalised in
later sprints (allowed by O1.4 acceptance).

## Regenerate

```bash
pip install pyyaml
python scripts/gen_openapi.py
```

## View the docs site

**No toolchain (fastest):** serve this folder and open `index.html`:

```bash
python -m http.server 8080 --directory docs/api
# open http://localhost:8080/index.html  → pick a service from the dropdown
```

**With Redocly (lint + static build):**

```bash
npm --prefix docs install          # installs @redocly/cli
npm --prefix docs run lint         # lints all 13 contracts
npm --prefix docs run build        # static HTML per service into docs/api/_site/
npm --prefix docs run preview      # live preview of the gateway spec
```

## Sign-off (O1.4 acceptance)

| Reviewer | Area | Status |
|----------|------|--------|
| Grace | Frontend | ☐ pending |
| Daniel | Chat | ☐ pending |
