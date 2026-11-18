# Free hosting and login

Selected host: Streamlit Community Cloud. Its official documentation describes free deployment from GitHub repositories. Netlify does not directly run this Python Streamlit app; its documented Server runtime is Node.js. No paid hosting, paid tier or credit-card flow is required by this plan.

## Accounts in this application
- Owner: private household workspace. Keep this password private.
- Demo: each browser session receives its own temporary copy of public REWD-P history, illustrative prices and sample appliances. Visitors can change their own session but cannot change the owner's records or another visitor's session. This is historical example data, not the owner's bills or a live forecast for a visitor's home.
- Wrong credentials are rejected. Password verification runs on the server with salted PBKDF2 hashes, constant-time digest comparison, shared per-account attempt throttling, a two-hour session expiry and a sign-out action. Throttling is process-local; this small single-instance academic login is not an enterprise identity service.

## Before deployment
Use only the files from the clean handoff ZIP. Never upload `.local`, `.streamlit/secrets.toml`, personal consumer CSVs, original datasets or bill photos. The clean package includes forecasting/OCR models and no real household records. A public dataset demo is included and identified as such.

1. Put the clean source in the intended GitHub repository. Confirm which GitHub account is being used before creating a repository.
2. Sign into Streamlit Community Cloud with GitHub. If new account terms or permissions require consent, the account owner must complete that step.
3. Create an app with entry point **cloud_app.py**, Python3.12, and the desired free subdomain.
4. Open Advanced settings → Secrets. Copy the full content of your private `.local/CLOUD_SECRETS.toml` into this private settings field, never into a repository file. Do not send these values in chat.
5. Deploy, then test wrong credentials, owner sign-in, two independent demo browser sessions, and logout. Until these live checks pass, the deployment is not verified.

`cloud_app.py` requires login and stops if the private account configuration is missing or malformed. Do not deploy app.py as the public entry point: app.py also supports an intentional local development mode without accounts.

## Local use
Run `python src/create_login_accounts.py` once (the helper refuses to overwrite existing accounts). This creates `.local/auth.json` with hashes and local-only credential instructions. These files are ignored by Git and excluded from the handoff builder. Existing local accounts automatically enable login in app.py.

## Persistence and limits
Free hosting has resource limits and may sleep/restart. Session work and local CSV edits on a cloud instance are not durable storage: restarting or redeploying can lose them. Keep the authoritative personal prototype and its backups on your laptop. The hosted demo can regenerate public example data on login. Durable online personal data storage would be a separate feature and is not claimed here.

No paid subscription, database, external authentication provider or Netlify service was created. Deployment preparation is not proof of a live hosted URL.

Sources:
- https://docs.streamlit.io/deploy/streamlit-community-cloud
- https://docs.streamlit.io/deploy/streamlit-community-cloud/deploy-your-app/secrets-management
- https://docs.netlify.com/build/server/overview/
