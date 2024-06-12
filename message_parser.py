
import os, time
from slack_bolt import App
from slack_sdk import WebClient
from datetime import datetime, timedelta

class SlackMessageChecker:
    """A class to check for old messages from a user in a Slack channel."""

    SLACK_MESSAGE_AGE_LIMIT = 1 # days - older than messages will be printed
    SLACK_CHANNEL_HISTORY_AGE_LIMIT = 30 # days - how far back to fetch messages

    def __init__(self, bot_token, channel_id, user_id):
        self.app = App(token=bot_token)
        self.client = WebClient(token=bot_token)
        self.channel_id = channel_id
        self.user_id = user_id
        self.__epoch_time_days_ago = self.__get_epoch_time_days_ago()   # how far back to fetch messages

    def __get_epoch_time_days_ago(self):
        """Get the Unix epoch time for the given number of days ago."""
        seconds_ago = self.SLACK_CHANNEL_HISTORY_AGE_LIMIT * 24 * 60 * 60
        current_time = time.time()
        target_time = current_time - seconds_ago
        return int(target_time)

    def __is_older_than_days(self, ts):
        """Check if a message is older than 5 days."""
        message_time = datetime.fromtimestamp(float(ts))
        return datetime.now() - message_time > timedelta(days=self.SLACK_MESSAGE_AGE_LIMIT)

    def __fetch_messages_from_user(self):
        """Fetch all messages from a user in a channel from the last X days."""
        messages = []
        cursor = None
        while True:
            response = self.client.conversations_history(channel=self.channel_id, cursor=cursor, limit=999, inclusive=True, oldest=self.__epoch_time_days_ago)
            messages.extend(response['messages'])
            cursor = response.get('response_metadata', {}).get('next_cursor')
            if not cursor:
                break
        user_messages = [msg for msg in messages if msg.get('user') == self.user_id]
        return user_messages

    def check_old_messages(self):
        """Check for messages older than X days from a user in a channel."""
        messages = self.__fetch_messages_from_user()
        for message in messages:
            if self.__is_older_than_days(message['ts']):
                print(f"Message from {self.user_id} older than {self.SLACK_MESSAGE_AGE_LIMIT} days: {message['text']}")

if __name__ == "__main__":
    # Extract channel ID and user ID from environment variables
    bot_token = os.environ.get('SLACK_BOT_TOKEN')
    channel_id = os.environ.get('SLACK_CHANNEL_ID')
    user_id = os.environ.get("SLACK_USER_ID")

    if bot_token and channel_id and user_id:
        checker = SlackMessageChecker(bot_token, channel_id, user_id)
        checker.check_old_messages()
    else:
        print("Please set the SLACK_BOT_TOKEN, SLACK_CHANNEL_ID, and SLACK_USER_ID environment variables.")
