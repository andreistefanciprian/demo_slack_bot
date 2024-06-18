
## Description

### Prerequisites
* A Slack workflow that collects user information in a Slack channel.
* A dedicated watchlist Slack channel to track older threads from the main channel.
* Slack Bot based on slack_app_manifest.yaml

### Functionality
* SlackWorkflowBot:
    - Creates a GitHub issue and posts it in response when the workflow is triggered by users.
* SlackWatchlistBot:
    - Parses workflow threads older than a specified number of days within the last specified number of days.
    - For matched threads, checks if the GitHub issue is open, labels it with a "watchlist" label, and posts a message with the thread in the watchlist Slack channel.

## Run app

```
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

export SLACK_CHANNEL_ID=<SLACK_CHANNEL_ID>
export SLACK_WATCHLIST_CHANNEL_ID=<SLACK_WATCHLIST_CHANNEL_ID>
export SLACK_BOT_TOKEN=<xoxb-SLACK_BOT_TOKEN>
export SLACK_USER_ID=<SLACK_USER_ID>
export SLACK_APP_TOKEN=<xapp-SLACK_APP_TOKEN>
export SLACK_BOT_ID=<SLACK_BOT_ID>
export GITHUB_REPO=<gh_user/repo_name>
export GITHUB_TOKEN=<ghp_GITHUB_TOKEN>
export LOG_LEVEL=DEBUG  # Optional. INFO log level set by default

# start SlackWatchlistBot
python main.py

# start SlackWorkflowBot
python workflow_bot.py
```

## Run app from container

```
# make sure .env is populated with env vars

# run from container
docker-compose up

# or kubernetes cronjob
kubectl create secret generic watchlist-slack-bot-secrets --from-env-file=.env
kubectl apply -f infra/cronjob.yaml
kubectl create job --from=cronjob/watchlist-slack-bot watchlist-slack-bot-init
```
