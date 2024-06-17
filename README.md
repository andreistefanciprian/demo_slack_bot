
## Description
Have a Slack workflow in place that collects information from users in a slack channel.
Have a watchlist slack channel, where older threads from main channel will be tracked.

The code will do the following:
* Create Github issue and post it as response when Workflow is triggered by users.
* Parse Workflow threads older than x days from the last y days.
* For matched threads, check if Github issue is open, label it with watchlist label and post a message with the thread in the watchlist slack channel.


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

python main.py
```
