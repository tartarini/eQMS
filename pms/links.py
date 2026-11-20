"""Recognise links to issues in external bug trackers, so a report can point at an issue that
someone has already raised. No network calls: the link is stored as given, with a readable
reference (for example ``owner/repo#12``) worked out from its address."""
import re
from urllib.parse import urlparse

GITHUB = re.compile(r"^/(?P<owner>[\w.-]+)/(?P<repo>[\w.-]+)/(?:issues|pull)/(?P<n>\d+)/?$")
GITLAB = re.compile(r"^/(?P<project>[\w./-]+?)/-/(?:issues|merge_requests)/(?P<n>\d+)/?$")
BITBUCKET = re.compile(r"^/(?P<owner>[\w.-]+)/(?P<repo>[\w.-]+)/issues/(?P<n>\d+)/?$")
JIRA = re.compile(r"^/browse/(?P<key>[A-Z][A-Z0-9_]+-\d+)/?$")

PROVIDER_LABELS = {"github": "GitHub", "gitlab": "GitLab", "bitbucket": "Bitbucket",
                   "jira": "Jira", "other": "Other tracker"}


def parse_issue_url(url: str):
    """Return (provider, reference) for a link to an issue. Anything that is not an https link
    with a host is refused with ValueError; other https links are kept as "other"."""
    parts = urlparse(url.strip())
    if parts.scheme != "https" or not parts.hostname:
        raise ValueError("The link must start with https:// and name a website.")
    host, path = parts.hostname.lower(), parts.path
    if host == "github.com" and (m := GITHUB.match(path)):
        return "github", f"{m['owner']}/{m['repo']}#{m['n']}"
    if "gitlab" in host and (m := GITLAB.match(path)):
        return "gitlab", f"{m['project']}#{m['n']}"
    if host == "bitbucket.org" and (m := BITBUCKET.match(path)):
        return "bitbucket", f"{m['owner']}/{m['repo']}#{m['n']}"
    if m := JIRA.match(path):
        return "jira", m["key"]
    return "other", f"{host}{path}"[:200]
