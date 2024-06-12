
## Description

Parse slack messages that are older than x days from the last y days belonging to user id.

## Run app

```
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

export SLACK_CHANNEL_ID=<SLACK_CHANNEL_ID>
export SLACK_BOT_TOKEN=<xoxb-SLACK_BOT_TOKEN>
export SLACK_SIGNING_SECRET=<SLACK_SIGNING_SECRET>
export SLACK_USER_ID=<SLACK_USER_ID>
export LOG_LEVEL=DEBUG  # INFO is set by default

python message_parser.py
```
