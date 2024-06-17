import os
import time
import logging
from slack_bolt import App
from slack_bolt.adapter.socket_mode import SocketModeHandler
from slack_sdk import WebClient
from datetime import datetime, timedelta
import requests


class SlackMessageChecker:
    """A class to check for messages older than a specified number of days from a user in a Slack channel."""

    SLACK_MESSAGE_AGE_LIMIT = 0  # days - older than messages will be printed
    SLACK_CHANNEL_HISTORY_AGE_LIMIT = 30  # days - how far back to fetch messages

    def __init__(self, bot_token, app_token, channel_id, user_id, github_token, github_repo):
        # Slack SDK
        self.app = App(token=bot_token)
        self.client = WebClient(token=bot_token)
        self.channel_id = channel_id
        self.user_id = user_id
        self.__debug_level = logging.getLevelName(os.getenv("LOG_LEVEL", "INFO"))  # Set logging level from env var. Eg: export LOG_LEVEL=DEBUG
        self.__setup_logging()  # Setup logging
        self.handler = SocketModeHandler(self.app, app_token)
        # Github API
        self.github_token = github_token
        self.github_repo = github_repo
        self.__api_url = f'https://api.github.com/repos/{github_repo}/issues'
        self.__headers = {
            'Authorization': f'token {self.github_token}',
            'Accept': 'application/vnd.github.v3+json'
        }
        self.__register_handlers()

    def __setup_logging(self):
        logging.basicConfig(
            format="%(levelname)s:%(asctime)s:%(message)s", level=self.__debug_level
        )

    def __get_epoch_time_days_ago(self):
        """
        Get the Unix epoch time for the given number of days ago.
        The return value will be used to fetch messages from the last X days.
        """
        seconds_ago = self.SLACK_CHANNEL_HISTORY_AGE_LIMIT * 24 * 60 * 60
        current_time = time.time()
        target_time = current_time - seconds_ago
        return int(target_time)

    def __is_older_than_days(self, ts):
        """Check if a message is older than x days."""
        message_time = datetime.fromtimestamp(float(ts))
        return datetime.now() - message_time > timedelta(days=self.SLACK_MESSAGE_AGE_LIMIT)

    def __fetch_messages_from_user(self):
        """Fetch all messages from a user in a channel from the last X days."""
        messages = []
        cursor = None
        while True:
            response = self.client.conversations_history(channel=self.channel_id, cursor=cursor, limit=999, inclusive=True, oldest=self.__get_epoch_time_days_ago())
            messages.extend(response['messages'])
            cursor = response.get('response_metadata', {}).get('next_cursor')
            if not cursor:
                break
        user_messages = [msg for msg in messages if msg.get('user') == self.user_id]
        logging.debug(f"Found {len(user_messages)} messages older than {self.SLACK_MESSAGE_AGE_LIMIT} day(s), from {self.user_id} in channel {self.channel_id}. Fetched messages are from the last {self.SLACK_CHANNEL_HISTORY_AGE_LIMIT} day(s).")
        return user_messages

    def __close_slack_thread(self, thread_ts):
        """Closes a Slack thread by posting a closing message."""
        closing_message = "This thread is now closed due to inactivity."
        response = self.client.chat_postMessage(
            channel=self.channel_id,
            text=closing_message,
            thread_ts=thread_ts
        )
        if response["ok"]:
            logging.info(f"Successfully closed thread with ts: {thread_ts}")
        else:
            logging.error(f"Failed to close thread with ts: {thread_ts}")

    def check_old_messages(self):
        """Check for messages older than X days from a user in a channel."""
        messages = self.__fetch_messages_from_user()
        for message in messages:
            if self.__is_older_than_days(message['ts']):
                logging.info(f"Message from {self.user_id} older than {self.SLACK_MESSAGE_AGE_LIMIT} days: {message['text']}")
                # self.__close_slack_thread(message['ts'])

    def __fetch_threads_from_user(self):
        """Fetch all threads started by a user in a channel from the last X days."""
        messages = self.__fetch_messages_from_user()
        logging.info(f"Found {len(messages)} messages from {self.user_id} in channel {self.channel_id}.")
        threads = [msg for msg in messages if 'thread_ts' in msg and msg['ts'] == msg['thread_ts']]
        logging.info(f"Found {len(threads)} threads started by {self.user_id} in channel {self.channel_id}.")
        return threads

    def check_old_threads(self):
        """Check for threads older than X days from a user in a channel and close them if they are old."""
        threads = self.__fetch_threads_from_user()
        for thread in threads:
            if self.__is_older_than_days(thread['ts']):
                logging.info(f"Thread from {self.user_id} older than {self.SLACK_MESSAGE_AGE_LIMIT} days: {thread['text']}")
                self.__close_slack_thread(thread['ts'])

    def __register_handlers(self):
        @self.app.command("/hello-socket-mode")
        def hello_command(ack, body):
            user_id = body["user_id"]
            ack(f"Hi, <@{user_id}>!")

        @self.app.event("app_mention")
        def event_test(event, say):
            user_id = event["user"]
            # Create a github issue
            title = 'Example Issue Title'
            body = 'This is an example issue body.'
            labels = ['bug', 'help wanted']
            assignees = ['andreistefanciprian']
            github_issue = self.__create_github_issue(title, body, labels, assignees)
            issue_url = github_issue.get('html_url', 'No URL found')
            say(f"Hi there, <@{user_id}>! We created Github issue <{issue_url}|{title}> fr you!")

        @self.app.message()
        def handle_workflow_message(message, say):
            logging.debug(f"Received message: {message}")
            if message['username'] == "Support Ticket Helper Bot":
                user_id = message["blocks"][0]["elements"][0]["elements"][8]["user_id"]
                # timestamp = message['ts']
                text = message['text']
                # Create github issue
                title = 'Example Issue Title'
                body = text
                labels = ['bug', 'help wanted']
                assignees = ['andreistefanciprian']
                github_issue = self.__create_github_issue(title, body, labels, assignees)
                issue_url = github_issue.get('html_url', 'No URL found')
                say(f"Hi there, <@{user_id}>! We created Github issue <{issue_url}|{title}> for you!")
    
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
            logging.info('Successfully created issue.')
        else:
            logging.info(f'Failed to create issue. Status code: {response.status_code}')
            logging.debug(response.json())
        return response.json()

    def start(self):
        """Start the Socket Mode handler to listen for events."""
        self.handler.start()


if __name__ == "__main__":
    # Extract tokens and IDs from environment variables
    slack_bot_token = os.environ.get('SLACK_BOT_TOKEN')
    slack_app_token = os.environ.get('SLACK_APP_TOKEN')
    slack_channel_id = os.environ.get('SLACK_CHANNEL_ID')
    slack_user_id = os.environ.get("SLACK_USER_ID")
    github_repo = os.environ.get("GITHUB_REPO")
    github_token = os.environ.get("GITHUB_TOKEN")

    if slack_bot_token and slack_app_token and slack_channel_id and slack_user_id:
        checker = SlackMessageChecker(slack_bot_token, slack_app_token, slack_channel_id, slack_user_id, github_token, github_repo)
        # checker.check_old_messages()
        checker.check_old_threads()
        checker.start()
    else:
        print("Please set the SLACK_BOT_TOKEN, SLACK_APP_TOKEN, SLACK_CHANNEL_ID, SLACK_USER_ID, GITHUB_REPO and GITHUB_TOKEN environment variables.")
