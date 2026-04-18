# Ad Prompt Assembler (No Copy Generation)

This repo’s playbook defines *what to do*. These scripts make it repeatable at scale.

## Workflow

1) Generate fresh copy externally (LLM/operator) into a JSON batch (see `scripts/copy_batch_example.json`).
2) Assemble prompts + backgrounds + safe-zones + registry:

```bash
python3 scripts/generate_ads.py --copy-file path/to/copy_batch.json
```

3) Submit EN prompts for image generation (default behavior of the Kie runner):

```bash
python3 scripts/kie_nano_batch.py --batch vN
```

## Enforcing “fresh copy” with an LLM

- The assembler enforces **exact-string uniqueness** by checking against `AD_GENERATION_REGISTRY.JSON -> indexes.used_text`.
- If a string was ever used (headline/support/cta/bullets), the assembler fails fast and tells you which field collided.
- Your LLM step should regenerate only the collided fields and re-run the assembler.

To help your LLM avoid repeats, export a banlist:

```bash
python3 scripts/registry_banlist.py --last 200 > banned_strings.json
```

Then include those strings in your LLM prompt as “Do not output any of these exact strings”.

