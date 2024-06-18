import os
import time
import logging
from slack_bolt import App
from slack_bolt.adapter.socket_mode import SocketModeHandler
from slack_sdk import WebClient
from datetime import datetime, timedelta
import requests
import re


class SlackWatchlistBot:
    """
    Check for Slack Bot threads older than a specified number of days.
    If there is a match, check Github issue is open, add a label and send a message to the watchlist channel.
    """

    SLACK_MESSAGE_AGE_LIMIT = 0  # days - older than messages will be printed
    SLACK_CHANNEL_HISTORY_AGE_LIMIT = 1  # days - how far back to fetch messages
    WATCHLIST_LABEL = 'watchlist'

    def __init__(self):
        # Set logging level from env var. Eg: export LOG_LEVEL=DEBUG
        self.__debug_level = logging.getLevelName(os.getenv("LOG_LEVEL", "INFO"))
        self.__setup_logging()  # Setup logging
        
        # Load configuration from environment variables
        self.bot_token = os.getenv('SLACK_BOT_TOKEN')
        self.app_token = os.getenv('SLACK_APP_TOKEN')
        self.channel_id = os.getenv('SLACK_CHANNEL_ID')
        self.watchlist_channel_id = os.getenv('SLACK_WATCHLIST_CHANNEL_ID')
        self.bot_id = os.getenv("SLACK_BOT_ID")
        self.github_token = os.getenv("GITHUB_TOKEN")
        self.github_repo = os.getenv("GITHUB_REPO")
        
        # Validate environment variables
        self.__validate_env_vars()

        # Slack SDK
        self.app = App(token=self.bot_token)
        self.client = WebClient(token=self.bot_token)
        self.handler = SocketModeHandler(self.app, self.app_token)

        # Github API
        self.__github_api_url = f'https://api.github.com/repos/{self.github_repo}/issues'
        self.__github_http_url =  f'https://github.com/{self.github_repo}/issues'
        self.__github_headers = {
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
            "SLACK_WATCHLIST_CHANNEL_ID": self.watchlist_channel_id,
            "SLACK_BOT_ID": self.bot_id,
            "GITHUB_TOKEN": self.github_token,
            "GITHUB_REPO": self.github_repo,
        }
        missing_vars = [var for var, value in required_vars.items() if value is None]
        if missing_vars:
            missing_vars_str = ", ".join(missing_vars)
            raise EnvironmentError(f"Missing required environment variables: {missing_vars_str}")

    def __get_epoch_time_days_ago(self):
        """
        Get the Unix epoch time for the given number of days ago.
        The return value will be used to fetch messages from the last SLACK_CHANNEL_HISTORY_AGE_LIMIT days.
        """
        seconds_ago = self.SLACK_CHANNEL_HISTORY_AGE_LIMIT * 24 * 60 * 60
        current_time = time.time()
        target_time = current_time - seconds_ago
        return int(target_time)

    def __is_timestamp_older_than_days(self, ts):
        """Check if a timestamp is older than SLACK_MESSAGE_AGE_LIMIT days."""
        message_time = datetime.fromtimestamp(float(ts))
        return datetime.now() - message_time > timedelta(days=self.SLACK_MESSAGE_AGE_LIMIT)

    def __send_slack_message(self, channel_id, thread_ts, message):
        """Post message in slack thread."""
        response = self.client.chat_postMessage(
            channel=channel_id,
            text=message,
            thread_ts=thread_ts
        )
        # print(response)
        if response["ok"]:
            logging.info(f"Successfully posted message in thread with ts: {thread_ts}")
        else:
            logging.error(f"Failed to post message in thread with ts: {thread_ts}")

    def __get_slack_message_permalink(self, channel_id, message_ts):
        """Get permalink for a slack message."""
        try:
            response = self.client.chat_getPermalink(channel=channel_id, message_ts=message_ts)
            if response["ok"]:
                return response["permalink"]
            else:
                print(f"Error getting permalink: {response['error']}")
                return None
        except Exception as e:
            print(f"Exception occurred: {e}")
            return None
    
    def __fetch_slack_messages_from_channel(self):
        """Fetch all messages from a workflow in a channel from the last SLACK_CHANNEL_HISTORY_AGE_LIMIT days."""
        messages = []
        cursor = None
        while True:
            response = self.client.conversations_history(channel=self.channel_id, cursor=cursor, limit=999, inclusive=True, oldest=self.__get_epoch_time_days_ago())
            messages.extend(response['messages'])
            cursor = response.get('response_metadata', {}).get('next_cursor')
            if not cursor:
                break
        logging.debug(f"Found {len(messages)} messages from the workflow in channel {self.channel_id}.")
        return messages

    def __is_slack_workflow_message_sent_by_bot(self, message):
        """Check if a message is from a workflow bot."""
        if 'subtype' in message.keys() and message['subtype'] == 'bot_message' and message['bot_id'] == self.bot_id:
            return True
        return False

    def __get_github_issue_number_from_text(self, text):
        """Extract GitHub issue number from text."""
        match = re.search(r'/issues/(\d+)', text)
        if match:
            return match.group(1)
        return None  

    def __github_issue_has_label(self, issue_number, label):
        """Check if a GitHub issue already has a specific label."""
        url = f'{self.__github_api_url}/{issue_number}'
        response = requests.get(url, headers=self.__github_headers)
        if response.status_code == 200:
            issue_data = response.json()
            labels = [lbl['name'] for lbl in issue_data.get('labels', [])]
            return label in labels
        else:
            logging.error(f"Failed to fetch issue {issue_number}. Status code: {response.status_code}")
            logging.debug(response.json())
            return False

    def __get_github_issue_number_from_slack_bot_reply(self, thread_ts):
        """Return Github issue number posted by Slack Support Bot in the first reply of the Slack Workflow thread."""
        try:
            response = self.client.conversations_replies(channel=self.channel_id, ts=thread_ts)
            if response["ok"]:
                replies = response["messages"]
                if len(replies) > 1:
                    first_reply = replies[1]  # The first reply (replies[0] is the original message)
                    issue_number = self.__get_github_issue_number_from_text(first_reply['text'])
                    if issue_number:
                        return issue_number
                    else:
                        logging.info(f"No GitHub issue number found in the first reply of thread {thread_ts}")
                        return None
                else:
                    logging.info(f"No replies in thread {thread_ts}")
                    return None
            else:
                logging.error(f"Failed to fetch replies for thread {thread_ts}: {response['error']}")
                return None
        except Exception as e:
            logging.error(f"Exception occurred while fetching replies for thread {thread_ts}: {str(e)}")
            return None

    def parse_slack_idle_workflow_threads(self):
        """Check for workflow threads older than SLACK_MESSAGE_AGE_LIMIT days."""
        messages = self.__fetch_slack_messages_from_channel()
        for message in messages:
            if self.__is_slack_workflow_message_sent_by_bot(message):
                if self.__is_timestamp_older_than_days(message['ts']):
                    logging.info(f"Workflow message older than {self.SLACK_MESSAGE_AGE_LIMIT} days: {message['text']}")
                    github_issue_number = self.__get_github_issue_number_from_slack_bot_reply(message['ts'])
                    if github_issue_number is not None:
                        github_issue_https_url = os.path.join(self.__github_http_url, github_issue_number)
                        if self.__is_github_issue_open(github_issue_number):
                            if not self.__github_issue_has_label(github_issue_number, self.WATCHLIST_LABEL):
                                self.__label_github_issue(github_issue_number, self.WATCHLIST_LABEL)
                                thread_id = message['ts']
                                self.__send_slack_message(self.channel_id, thread_id, "This thread is now being monitored in the watchlist channel due to inactivity.")
                                self.__send_slack_message(self.watchlist_channel_id, None, f"{self.__get_slack_message_permalink(self.channel_id, thread_id)}")
                            else:
                                logging.info(f"{github_issue_https_url} already has the {self.WATCHLIST_LABEL} label.")
                        else:
                            logging.info(f"{github_issue_https_url} is not open, no label added.")
              

    def __is_github_issue_open(self, issue_number):
        """Check if a GitHub issue is open. Return True if open, False if closed."""
        url = f'{self.__github_api_url}/{issue_number}'
        response = requests.get(url, headers=self.__github_headers)
        if response.status_code == 200:
            issue_data = response.json()
            return issue_data['state'] == 'open'
        else:
            logging.error(f"Failed to fetch issue {issue_number}. Status code: {response.status_code}")
            logging.debug(response.json())
            return False

    def __label_github_issue(self, issue_number, label):
        """Add a label to a GitHub issue."""
        url = f'{self.__github_api_url}/{issue_number}/labels'
        data = {'labels': [label]}
        github_issue_https_url = os.path.join(self.__github_http_url, issue_number)
        response = requests.post(url, json=data, headers=self.__github_headers)
        if response.status_code == 200 or response.status_code == 201:
            logging.info(f'Successfully added label {label} to issue {github_issue_https_url}.')
        else:
            logging.error(f"Failed to add label to issue {github_issue_https_url}. Status code: {response.status_code}")
            logging.debug(response.json())

    def start(self):
        """Start the Socket Mode handler to listen for events."""
        self.handler.start()


if __name__ == "__main__":
    try:
        checker = SlackWatchlistBot()
        checker.parse_slack_idle_workflow_threads()
        checker.start()
    except EnvironmentError as e:
        logging.error(str(e))