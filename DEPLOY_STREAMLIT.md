# Deploy the CBB Intelligence Terminal

## 1. Push the website to GitHub

This is a **separate website repository** from the MLB HR dashboard. A suggested repository name is `cbb-model-dashboard`.

From the project folder:

```bash
bash bootstrap_github.sh
```

The script initializes Git if necessary, commits the project, and—when the GitHub CLI (`gh`) is installed and authenticated—can create and push the repository. If `gh` is unavailable, it prints the manual commands instead.

Never commit `.streamlit/secrets.toml`.

## 2. Create Supabase persistence

Create a Supabase project, open **SQL Editor**, paste the full contents of `supabase/schema.sql`, and run it once.

The application prefers current Supabase keys:

- publishable key (`sb_publishable_...`) for public reads;
- secret key (`sb_secret_...`) for server-side admin writes.

The code also accepts legacy anon / service-role key names as fallbacks.

## 3. Deploy to Streamlit Community Cloud

Create a new Streamlit app from the CBB GitHub repository:

- branch: `main`
- entrypoint: `app.py`
- choose a distinct CBB subdomain, for example `cbb-model-dashboard.streamlit.app` if available.

Do not reuse the HR Streamlit application; this dashboard is intentionally separate.

## 4. Create the Google OAuth web client

After the Streamlit app URL is known, create a Google OAuth 2.0 **Web application** client and add this redirect URI exactly:

```text
https://YOUR-CBB-APP.streamlit.app/oauth2callback
```

The redirect must match the `[auth].redirect_uri` value in Streamlit secrets.

## 5. Add Streamlit secrets

Open **App settings → Secrets** and copy `STREAMLIT_SECRETS_TEMPLATE.toml`. Replace every placeholder. Generate a strong cookie secret locally, for example:

```bash
python3 -c "import secrets; print(secrets.token_urlsafe(48))"
```

Keep the Supabase secret key and Google client secret only in Streamlit's secrets manager.

## 6. Smoke test before sharing the URL

Open an incognito browser and verify that the public site exposes no uploader or Admin Studio. Then sign in with the allowlisted Google account, publish one V1.1 board, sign out, and confirm the slate remains readable in incognito. Publish the matching graded CSV after a completed historical slate and verify the Performance Laboratory updates.

Official references:

- https://docs.streamlit.io/develop/api-reference/user/st.login
- https://docs.streamlit.io/develop/tutorials/authentication/google
- https://supabase.com/docs/guides/getting-started/api-keys
- https://supabase.com/docs/guides/database/secure-data
