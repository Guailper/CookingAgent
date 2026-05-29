# Upload Ingestion Evaluation Samples

Run this command from the repository root to recreate the sample files:

```powershell
conda run -n cook-agent python backend\eval\upload_ingest_samples\generate_samples.py
```

Use the generated files to manually verify:

- upload whitelist behavior
- MinerU parsing
- content validation model classification
- knowledge-base indexing
- retry behavior after failed validation, parsing, or indexing

Expected outcomes are listed in `manifest.json`.
