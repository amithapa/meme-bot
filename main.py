import os
import re
import hmac
import hashlib
import requests

from fastapi import FastAPI, HTTPException, Header, Request
from github import Github, GithubIntegration


app = FastAPI()


app_id = "224361"
GITHUB_SECRET: str = os.environ.get("WEBHOOK_SECRET", "")

with open("./.env/bot_key.pem", "r") as cert_file:
    app_key = cert_file.read()

# Create an github integration instance
git_integration = GithubIntegration(app_id, app_key)


def calculate_signature(github_signature: str, payload: bytes) -> str:
    """
    Signature calculator
    """
    signature_bytes = bytes(github_signature, "utf-8")
    digest = hmac.new(key=signature_bytes, msg=payload, digestmod=hashlib.sha256)
    signature = digest.hexdigest()
    print(f"Calculated signature: {signature}")
    return signature


@app.post("/")
async def bot(
    request: Request,
    x_github_event: str = Header(default=None),
    x_hub_signature_256: str = Header(default=None),
):

    if x_hub_signature_256 is None:
        raise HTTPException(status_code=403)

    body = await request.body()

    incoming_signature = re.sub(r"^sha256=", "", x_hub_signature_256)
    calculated_signature = calculate_signature(GITHUB_SECRET, body)

    if incoming_signature != calculated_signature:
        raise HTTPException(status_code=403)
    else:
        print("Authorized access")

    if x_github_event is None:
        return "Ok"

    # Get the event payload
    payload = await request.json()
    # Check if the event is a Github PR creation event
    if payload["action"] != "opened":
        return "Ok"

    base_branch = payload["pull_request"]["base"]["ref"]
    head_branch = payload["pull_request"]["head"]["ref"]

    print(base_branch, head_branch)

    owner = payload["repository"]["owner"]["login"]
    repo_name = payload["repository"]["name"]

    # Get a git connection as our bot
    # Here is where we are getting the permission to talk as our bot
    # and not as a Python webservice
    git_connection = Github(
        git_integration.get_access_token(
            git_integration.get_installation(owner, repo_name).id
        ).token
    )
    repo = git_connection.get_repo(f"{owner}/{repo_name}")

    issue = repo.get_issue(number=payload["pull_request"]["number"])

    # Call meme-api to get a random meme
    response = requests.get(url="https://meme-api.herokuapp.com/gimme")
    if response.status_code != 200:
        return "ok"

    # Get the best resolution meme
    meme_url = response.json()["preview"][-1]
    # Create a comment with a random meme
    issue.create_comment(f"![Alt Text]({meme_url})")
    return "ok"
