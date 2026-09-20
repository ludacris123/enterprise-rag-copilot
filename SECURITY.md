# Security Policy

Do not report vulnerabilities in public issues. Contact the repository owner privately.

Never commit API keys, JWT secrets, customer documents, production traces, or evaluation data containing personal information. Rotate any accidentally exposed credential immediately.

The demo authentication bypass is enabled only when `ENVIRONMENT=development`. Production deployments must use verified OIDC/JWT identities and deny startup when placeholder secrets are present.
