# CBB Dashboard v1.1 — Security & Publishing Setup

## Architecture

```text
Public visitor
    |
    +--> Today's Board        read only
    +--> Matchup Explorer     read only
    +--> Team Intelligence    read only
    +--> Performance Lab      read only
    +--> Model Guide          read only

Google OIDC login
    |
    +--> exact ADMIN_EMAIL match
            |
            +--> Admin Studio
                    +--> Upload V1.1 decision board
                    +--> Validate / preview
                    +--> Explicit Publish
                    +--> Upload V1.1 graded board
                    +--> Validate / preview
                    +--> Explicit Publish grading

Supabase Postgres
    |
    +--> public SELECT through RLS
    +--> no public INSERT / UPDATE / DELETE policy
    +--> server-side secret-key writes only
```

## Google authentication

Streamlit's native login flow uses OpenID Connect. Create a Google OAuth 2.0 **Web application** credential. The authorized redirect URI must be the deployed Streamlit application's absolute URL plus `/oauth2callback`.

Example:

```text
https://YOUR-CBB-APP.streamlit.app/oauth2callback
```

`ADMIN_EMAIL` in Streamlit secrets is the only owner account allowed to enter Admin Studio. Other authenticated users remain read-only. The app also rejects an expired identity claim when `exp` is provided and rejects `email_verified=false`.

## Supabase

Run `supabase/schema.sql` once in the new CBB Supabase project. The table `public.cbb_slates` has RLS enabled and grants public roles SELECT only. There are no public write policies.

The app prefers the current key names:

```toml
SUPABASE_PUBLISHABLE_KEY = "sb_publishable_..."
SUPABASE_SECRET_KEY = "sb_secret_..."
```

Legacy `SUPABASE_ANON_KEY` and `SUPABASE_SERVICE_ROLE_KEY` are supported as compatibility fallbacks.

The secret/service-role credential has elevated access and must never be committed or rendered. Put it only in Streamlit App Settings → Secrets.

## Publishing integrity

Each published board stores a SHA-256 hash and revision number. Re-publishing an identical board preserves compatible grading. Publishing changed same-date board data increments the revision and clears old grading so results cannot silently attach to a different prediction board.

Grading publication requires the exact same set of Game IDs as the published prediction board.

The stored audit actor is a one-way hash identifier; the Google email itself is not written to `cbb_slates`.

## Public smoke test

An incognito user should see only read-only navigation and an Admin sign-in action. There must be no uploader, publish button, database secret or Admin Studio page. An allowlisted owner should be able to sign in, publish, sign out, and see the persistent slate from another browser session.

Official references:

- https://docs.streamlit.io/develop/concepts/connections/authentication
- https://docs.streamlit.io/develop/api-reference/user/st.login
- https://supabase.com/docs/guides/getting-started/api-keys
- https://supabase.com/docs/guides/database/secure-data
