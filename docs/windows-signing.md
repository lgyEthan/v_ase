# Windows publisher signing

This is a setup guide, not an enabled feature. **v_ase 0.4.9 Windows downloads
remain unsigned.** No Windows signing account, certificate, secret or signing
configuration was added. Apple Developer ID and notarization cover only macOS.

## Choose a publisher identity first

Microsoft Artifact Signing (formerly Trusted Signing) is the straightforward
cloud option for an eligible publisher. Public Trust currently supports
organizations in Australia and South Korea among other listed regions, but
**individual developers must be located in the US or Canada**. A person publishing
as an individual in Australia/Korea should therefore check another certificate
provider, rather than create a fictitious organization. Use an institution's
identity only with its authorization. Private Trust is not a substitute for
public consumer distribution. See Microsoft's [eligibility and setup](https://learn.microsoft.com/en-us/azure/artifact-signing/quickstart).

For that service, prepare an Azure subscription and Entra tenant, register
`Microsoft.CodeSigning`, create an Artifact Signing account, complete identity
validation in the Azure portal, and create a **Public Trust** certificate profile.
Keep its region endpoint, account name, profile name and verified publisher CN.
[Microsoft setup](https://learn.microsoft.com/en-us/azure/artifact-signing/quickstart)

If ineligible, obtain an Authenticode code-signing certificate from a publicly
trusted CA that accepts your actual country and individual/organization status.
Before paying, ask the provider to confirm that eligibility, the exact publisher
name, Windows/Electron compatibility, and its CI-compatible hardware-token or
cloud-key workflow. An Apple certificate, TLS certificate or self-signed
certificate cannot establish this Windows publisher identity.

## Future integration in this repository

The host currently pins **electron-builder 26.15.3**. Its configuration uses
`win.azureSignOptions` for Azure, or `win.signtoolOptions` for conventional
SignTool signing. Do not copy the different signing schema from a newer builder
version. The following is a proposal for `desktop/package.json`, with placeholders;
it is deliberately absent from the actual build configuration:

```json
{
  "build": {
    "win": {
      "azureSignOptions": {
        "publisherName": "EXACT VERIFIED CERTIFICATE CN",
        "endpoint": "YOUR ACCOUNT REGION ENDPOINT",
        "codeSigningAccountName": "YOUR ACCOUNT NAME",
        "certificateProfileName": "YOUR PUBLIC TRUST PROFILE"
      }
    }
  }
}
```

Assign the signing identity the certificate-profile signing role. Builder 26
supports Entra credentials such as `AZURE_TENANT_ID`, `AZURE_CLIENT_ID` and
`AZURE_CLIENT_SECRET`; keep a secret in a protected GitHub release environment,
never in source, logs or a DMG/ZIP. The publisher name must match the certificate.
[Builder 26 signing configuration](https://www.electron.build/v26/docs/features/code-signing/code-signing-win/)

Microsoft also documents a GitHub Actions integration and multiple signing
backends. Prefer a short-lived federated identity where the selected integration
supports it; verify authentication with this pinned builder before adopting it.
A separate post-build action must still sign the installed executable and
installer contents in the correct order, not merely the outer installer.
[Microsoft signing integrations](https://learn.microsoft.com/en-us/azure/artifact-signing/how-to-signing-integrations)

For a commercial CA, use its supported key provider with the builder's SignTool
path. Confirm whether its certificate is hardware/cloud-backed; do not assume a
portable `.pfx` is available. Keep private keys out of GitHub artifacts. Evaluate
these details with the chosen provider before editing the release workflow.

## Required release checks once signing is authorized

1. Add signing only to the Windows release job in `.github/workflows/desktop.yml`.
   Preserve the existing tests and Mac signing process. Fail a release when
   expected credentials/signatures are missing; do not fall back to unsigned.
2. Audit the portable app, NSIS installed app and uninstaller, plus executable
   dependencies in the bundled Python runtime. Preserve existing third-party
   signatures and account for any unsigned executable components.
3. Sign final executable bytes before packaging/signing their container. Use
   SHA-256 file digests and a trusted RFC 3161 timestamp, then create checksums.
   The Windows SDK supports verification such as:

   ```powershell
   signtool verify /pa /all /v "v_ase.exe"
   signtool verify /pa /all /v "v_ase-0.4.9-win-x64.exe"
   Get-AuthenticodeSignature ".\v_ase.exe" | Format-List Status,SignerCertificate,TimeStamperCertificate
   ```

   Require a valid chain, the intended publisher and timestamp; repeat against
   the installed copy. [SignTool reference](https://learn.microsoft.com/en-us/windows/win32/seccrypto/signtool)
4. Run `npm test`, `npm run smoke`, packaged tests and Windows association tests
   against the signed candidate. Re-download the public installer/ZIP, verify
   hashes and signatures again, and test installation on a clean Windows machine.
5. Update `docs/desktop.md`, README installation guidance, release notes and
   signing evidence only after successful verification. Python/PyPI and macOS
   signing are independent; do not describe them as Windows signing evidence.

## What signing does and does not solve

A valid signature identifies the publisher and detects changed executable bytes.
It does **not** guarantee that a new download avoids SmartScreen. Microsoft states
that EV certificates no longer grant an automatic SmartScreen bypass. Maintain a
consistent publisher identity and communicate the actual status. Store
distribution is a different publishing route, with Microsoft signing; it is not
required for the existing GitHub installer. Do not instruct users to disable
Windows security globally. [Microsoft SmartScreen guidance](https://learn.microsoft.com/en-us/windows/apps/package-and-deploy/smartscreen-reputation)
