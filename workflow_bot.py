import os
import logging
from slack_bolt import App
from slack_bolt.adapter.socket_mode import SocketModeHandler
from slack_sdk import WebClient
import requests


class SlackWorkflowBot: 
    """
    Create Github issue when Workflow is triggered and reply to thread.
    """

    def __init__(self):
        # Set logging level from env var. Eg: export LOG_LEVEL=DEBUG
        self.__debug_level = logging.getLevelName(os.getenv("LOG_LEVEL", "INFO"))
        self.__setup_logging()  # Setup logging
        
        # Load configuration from environment variables
        self.bot_token = os.getenv('SLACK_BOT_TOKEN')
        self.app_token = os.getenv('SLACK_APP_TOKEN')
        self.channel_id = os.getenv('SLACK_CHANNEL_ID')
        self.github_token = os.getenv("GITHUB_TOKEN")
        self.github_repo = os.getenv("GITHUB_REPO")
        
        # Validate environment variables
        self.__validate_env_vars()

        # Slack SDK
        self.app = App(token=self.bot_token)
        self.client = WebClient(token=self.bot_token)
        self.handler = SocketModeHandler(self.app, self.app_token)
        self.__register_slack_event_handlers()

        # Github API
        self.__api_url = f'https://api.github.com/repos/{self.github_repo}/issues'
        self.__headers = {
            'Authorization': f'token {self.github_token}',
            'Accept': 'application/vnd.github.v3+json'
        }

    def __setup_logging(self):
        logging.basicConfig(
            format="%(levelname)s:%(asctime)s:%(message)s", level=self.__debug_level
        )

    def __validate_env_vars(self):
        """Validate the required environment variables."""
        required_vars = {
            "SLACK_BOT_TOKEN": self.bot_token,
            "SLACK_APP_TOKEN": self.app_token,
            "SLACK_CHANNEL_ID": self.channel_id,
            "GITHUB_TOKEN": self.github_token,
            "GITHUB_REPO": self.github_repo,
        }
        missing_vars = [var for var, value in required_vars.items() if value is None]
        if missing_vars:
            missing_vars_str = ", ".join(missing_vars)
            raise EnvironmentError(f"Missing required environment variables: {missing_vars_str}")

    def __send_slack_message(self, channel_id, thread_ts, message):
        """Post message in slack thread."""
        response = self.client.chat_postMessage(
            channel=channel_id,
            text=message,
            thread_ts=thread_ts
        )
        if response["ok"]:
            logging.info(f"Successfully posted message in thread with ts: {thread_ts}")
        else:
            logging.error(f"Failed to post message in thread with ts: {thread_ts}")               

    def __register_slack_event_handlers(self):
        """Register message handler for workflow posts."""
        @self.app.message()
        def handle_workflow_reply(message):
            if message['username'] == "Support Ticket Helper Bot":
                user_id = message["blocks"][0]["elements"][0]["elements"][8]["user_id"]
                text = message['text']
                # Create github issue
                title = 'Example Issue Title'
                body = text
                labels = ['bug', 'help wanted']
                assignees = ['andreistefanciprian']
                github_issue = self.__create_github_issue(title, body, labels, assignees)
                issue_url = github_issue.get('html_url', 'No URL found')
                # Post reply in thread
                thread_id = message['ts']
                bot_reply = f"Hi there, <@{user_id}>! We created Github issue <{issue_url}|{title}> for you!"
                # bot_reply = f"Your issue has been posted on Github: <{issue_url}|{title}>. Please follow up using this link."
                self.__send_slack_message(self.channel_id, thread_id, bot_reply)
    
    def __create_github_issue(self, title, body=None, labels=None, assignees=None):
        """Creates Github issue."""
        issue = {
            'title': title,
            'body': body,
            'labels': labels if labels else [],
            'assignees': assignees if assignees else []
        }
        response = requests.post(self.__api_url, json=issue, headers=self.__headers)
        if response.status_code == 201:
            logging.info(f'Successfully created issue: {response.json()["html_url"]}')
        else:
            logging.info(f'Failed to create issue. Status code: {response.status_code}')
            logging.debug(response.json())
        return response.json()

    def start(self):
        """Start the Socket Mode handler to listen for events."""
        self.handler.start()


if __name__ == "__main__":
    try:
        checker = SlackWorkflowBot()
        checker.start()
    except EnvironmentError as e:
        logging.error(str(e))