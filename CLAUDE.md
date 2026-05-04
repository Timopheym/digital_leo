# digital_leo

## Langfuse

Credentials live in `.env` (gitignored): `LANGFUSE_PUBLIC_KEY`, `LANGFUSE_SECRET_KEY`, `LANGFUSE_BASE_URL`.

Always invoke the CLI from the project root with `--env .env`, e.g.:

```bash
npx langfuse-cli --env .env api datasets create --name <name>
npx langfuse-cli --env .env api dataset-items create --dataset-name <name> --input '{"q":"..."}' --expected-output '{"a":"..."}'
```

Project: `digital_tolstoy` (org `timopheym`).
