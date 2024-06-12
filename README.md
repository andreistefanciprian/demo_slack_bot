
## Run app

```
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

export SLACK_CHANNEL_ID=<SLACK_CHANNEL_ID>
export SLACK_BOT_TOKEN=<xoxb-SLACK_BOT_TOKEN>
export SLACK_SIGNING_SECRET=<SLACK_SIGNING_SECRET>
export SLACK_USER_ID=<SLACK_USER_ID>

python message_parser.py
```
