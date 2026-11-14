# Deployment checklist

## Stage this prototype privately first

1. Create a **private** GitHub repository within SERK Technologies and push the directory contents; assign least-privilege repository access.
2. Configure unique `ADMIN_TOKEN` and `DATABASE_PATH` using secret management. Do not use the example values.
3. Deploy behind TLS to a **staging** domain only; do not present it as an official Bureau service.
4. Restore test data into isolated staging DB, run automated tests, manually review sensitive cultural content and remove all real personal data from demonstration data.
5. Enable centralized logging with no secrets or unredacted story bodies; measure uptime and exception rates.
6. Perform external security, accessibility and privacy reviews before adding real users.

## Git bootstrap after repo creation

```bash
git init -b main
git add .
git commit -m "feat: initialize Visit Tigray digital tourism platform"
git remote add origin git@github.com:Serk-Technologies/visit-tigray.git
git push -u origin main
```

The remote above is a **proposed** repository name and does not indicate that it already exists.

## Future architecture migration

Use PostgreSQL and migration tooling before multi-instance operation; SQLite mounts are intentionally local-only. Put content media in permissioned object storage; implement editorial and legal approvals. Introduce OIDC, staff MFA, explicit administrator permission checks and high-quality audit logs before inviting Bureau employees. Booking services stay disabled until policies and safety conditions are approved.
