import os
import onesignal
from onesignal.api import default_api
from onesignal.model.notification import Notification
import logging

logger = logging.getLogger(__name__)

configuration = onesignal.Configuration(
    app_key=os.environ["DJANGO_DEMO_PUSH_API_KEY"],
)


def send_push_message(heading, content, recipient=False):
    if os.environ["DJANGO_DEMO"] == "0":
        return True
    if not recipient:
        recipient = os.environ["DJANGO_DEMO_PUSH_ALIAS_ID"]

    with onesignal.ApiClient(configuration) as api_client:
        api_instance = default_api.DefaultApi(api_client)
        notification = Notification()
        notification.app_id = os.environ["DJANGO_DEMO_PUSH_APP_ID"]
        notification.priority = 10
        notification.include_aliases = {
            'onesignal_id': [os.environ["DJANGO_DEMO_PUSH_ALIAS_ID"]]
        }
        notification.target_channel = "push"
        notification.headings = {
            "en": heading
        }
        notification.contents = {
            "en": content
        }

        try:
            api_response = api_instance.create_notification(notification)
            logger.info(f"OneSignal (success): {api_response}")
            print(api_response)
            return True
        except onesignal.ApiException as e:
            logger.error(f"OneSignal (error): {e}")
            print(e)
            return False
