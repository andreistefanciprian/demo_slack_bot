import os
import time
import logging
from slack_bolt import App
from slack_bolt.adapter.socket_mode import SocketModeHandler
from slack_sdk import WebClient
from datetime import datetime, timedelta
import requests
import re


class SlackMessageChecker:
    """
    Check for Slack Bot threads older than a specified number of days.
    If there is a match, check Github issue is open, add a label and send a message to the watchlist channel.
    Create Github issue when Workflow is triggered and reply to thread.
    """

    SLACK_MESSAGE_AGE_LIMIT = 0  # days - older than messages will be printed
    SLACK_CHANNEL_HISTORY_AGE_LIMIT = 1  # days - how far back to fetch messages

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
        self.__register_handlers()

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

    def __is_older_than_days(self, ts):
        """Check if a message is older than SLACK_MESSAGE_AGE_LIMIT days."""
        message_time = datetime.fromtimestamp(float(ts))
        return datetime.now() - message_time > timedelta(days=self.SLACK_MESSAGE_AGE_LIMIT)

    def __post_message_in_slack_thread(self, channel_id, thread_ts, message):
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

    def __get_message_permalink(self, channel_id, message_ts):
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
    
    def __fetch_messages_from_workflow(self):
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

    def __is_workflow_message(self, message):
        """Check if a message is from a workflow bot."""
        if 'subtype' in message.keys() and message['subtype'] == 'bot_message' and message['bot_id'] == self.bot_id:
            return True
        return False

    def __get_github_issue_number_from_url(self, url):
        """Extract GitHub issue number from URL."""
        match = re.search(r'/issues/(\d+)', url)
        if match:
            return match.group(1)
        return None

    def __get_github_issue_number_from_bot_reply(self, thread_ts):
        """Return Github issue number posted by Support Bot in the first reply of the Workflow Slack thread."""
        try:
            response = self.client.conversations_replies(channel=self.channel_id, ts=thread_ts)
            if response["ok"]:
                replies = response["messages"]
                if len(replies) > 1:
                    first_reply = replies[1]  # The first reply (replies[0] is the original message)
                    # logging.info(f"First reply in thread {thread_ts}: {first_reply['text']}")
                    attachments = first_reply.get('attachments', [])
                    if attachments:
                        issue_url = attachments[0].get('from_url', '')
                        issue_number = self.__get_github_issue_number_from_url(issue_url)
                        logging.info(f"GitHub issue number from the first reply: {issue_number}")
                        return issue_number
                    else:
                        logging.info(f"No attachments found in the first reply of thread {thread_ts}")
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

    def check_old_workflow_messages(self):
        """Check for messages older than SLACK_MESSAGE_AGE_LIMIT days from a workflow in a channel."""
        messages = self.__fetch_messages_from_workflow()
        for message in messages:
            if self.__is_workflow_message(message):
                if self.__is_older_than_days(message['ts']):
                    logging.info(f"Workflow message older than {self.SLACK_MESSAGE_AGE_LIMIT} days: {message['text']}")
                    github_issue_number = self.__get_github_issue_number_from_bot_reply(message['ts'])
                    if github_issue_number is not None:
                        if self.__is_github_issue_open(github_issue_number):
                            self.__add_label_to_github_issue(github_issue_number)
                            thread_id = message['ts']
                            self.__post_message_in_slack_thread(self.channel_id, thread_id, "This thread is now being monitored in the watchlist channel due to inactivity.")

                            self.__post_message_in_slack_thread(self.watchlist_channel_id, None, f"{self.__get_message_permalink(self.channel_id, thread_id)}")
                        else:
                            logging.info(f"Issue #{github_issue_number} is not open, no label added.")                 
  
    def __register_handlers(self):
        """Register message handler for workflow posts."""
        @self.app.message()
        def handle_workflow_posts(message):
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
                self.__post_message_in_slack_thread(self.channel_id, thread_id, bot_reply)
    
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

    def __is_github_issue_open(self, issue_number):
        """Check if a GitHub issue is open. Return True if open, False if closed."""
        url = f'{self.__api_url}/{issue_number}'
        response = requests.get(url, headers=self.__headers)
        if response.status_code == 200:
            issue_data = response.json()
            return issue_data['state'] == 'open'
        else:
            logging.error(f"Failed to fetch issue {issue_number}. Status code: {response.status_code}")
            logging.debug(response.json())
            return False

    def __add_label_to_github_issue(self, issue_number, label='watchlist'):
        """Add a label to a GitHub issue."""
        url = f'{self.__api_url}/{issue_number}/labels'
        data = {'labels': [label]}
        response = requests.post(url, json=data, headers=self.__headers)
        if response.status_code == 200 or response.status_code == 201:
            logging.info(f'Successfully added label {label} to issue #{issue_number}.')
        else:
            logging.error(f"Failed to add label to issue {issue_number}. Status code: {response.status_code}")
            logging.debug(response.json())

    def start(self):
        """Start the Socket Mode handler to listen for events."""
        self.handler.start()


if __name__ == "__main__":
    try:
        checker = SlackMessageChecker()
        checker.check_old_workflow_messages()
        checker.start()
    except EnvironmentError as e:
        logging.error(str(e))