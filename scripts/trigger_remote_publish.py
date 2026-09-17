"""
Dispatches the GitHub Actions publishing workflow with 0-second queue delay.
Can be invoked locally, via Windows Task Scheduler, or via cron-job.org webhook.

Usage:
  python scripts/trigger_remote_publish.py [--force] [--repo=OWNER/REPO]
"""
import sys
import os
import json
import subprocess
import requests

DEFAULT_REPO = "arunachalamvenkatachalapathy-dev/gk-reels"


def trigger_via_gh_cli(repo, force=False):
    """Triggers workflow via local gh CLI if available and authenticated."""
    cmd = ["gh", "workflow", "run", "publish.yml", "--repo", repo]
    if force:
        cmd.extend(["-f", "force=true"])
    try:
        res = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, check=True)
        print(f"[Trigger] Successfully dispatched via gh CLI:\n{res.stdout.strip()}")
        return True
    except Exception as e:
        print(f"[Trigger] gh CLI trigger failed: {e}")
        return False


def trigger_via_github_api(repo, token, force=False):
    """Triggers workflow via GitHub REST API (dispatches endpoint)."""
    url = f"https://api.github.com/repos/{repo}/actions/workflows/publish.yml/dispatches"
    headers = {
        "Authorization": f"Bearer {token}",
        "Accept": "application/vnd.github.v3+json"
    }
    payload = {
        "ref": "main",
        "inputs": {
            "force": force
        }
    }
    try:
        resp = requests.post(url, headers=headers, json=payload, timeout=20)
        if resp.status_code in (200, 204):
            print(f"[Trigger] Successfully dispatched {repo} via GitHub REST API (HTTP {resp.status_code})")
            return True
        else:
            print(f"[Trigger] GitHub API returned status {resp.status_code}: {resp.text}")
            return False
    except Exception as e:
        print(f"[Trigger] GitHub API request error: {e}")
        return False


def main():
    force = "--force" in sys.argv
    repo = DEFAULT_REPO
    for arg in sys.argv:
        if arg.startswith("--repo="):
            repo = arg.split("=", 1)[1]

    print(f"Triggering instant publish workflow on: {repo} (force={force})")

    token = os.environ.get("GITHUB_TOKEN") or os.environ.get("GH_TOKEN")
    if token:
        if trigger_via_github_api(repo, token, force=force):
            return

    if trigger_via_gh_cli(repo, force=force):
        return

    print("[Trigger] Failed to trigger workflow. Ensure either 'gh' CLI is authenticated or GITHUB_TOKEN is set.")
    sys.exit(1)


if __name__ == "__main__":
    main()
