"""SSO provider settings, built from environment variables. No Django imports: loaded by settings."""
import os


def configured_providers():
    """Provider settings for allauth, built only from providers with credentials set."""
    def creds(prefix):
        cid, secret = os.environ.get(f"{prefix}_CLIENT_ID"), os.environ.get(f"{prefix}_SECRET")
        return {"client_id": cid, "secret": secret} if cid and secret else None

    providers = {}
    if app := creds("SSO_GOOGLE"):
        providers["google"] = {"APPS": [app], "SCOPE": ["profile", "email"],
                               "AUTH_PARAMS": {"prompt": "select_account"}}
    if app := creds("SSO_MICROSOFT"):
        # "organizations" = any work/school account; set a tenant ID to restrict to one org.
        app["settings"] = {"tenant": os.environ.get("SSO_MICROSOFT_TENANT", "organizations")}
        providers["microsoft"] = {"APPS": [app]}
    if app := creds("SSO_GITHUB"):
        providers["github"] = {"APPS": [app], "SCOPE": ["read:user", "user:email"]}
    if app := creds("SSO_ORCID"):
        providers["orcid"] = {"APPS": [app],
                              "BASE_DOMAIN": os.environ.get("SSO_ORCID_DOMAIN", "orcid.org"),
                              "MEMBER_API": False}
    if app := creds("SSO_LINKEDIN"):
        app.update({"provider_id": "linkedin", "name": "LinkedIn",
                    "settings": {"server_url": "https://www.linkedin.com/oauth",
                                 "token_auth_method": "client_secret_post"}})
        providers["openid_connect"] = {"APPS": [app]}
    return providers
