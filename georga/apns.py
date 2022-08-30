from aioapns import APNs, NotificationRequest

from settings import APNS

apns_key_client = APNs(
    key=APNS.KEY_PATH,
    key_id=APNS.KEY_ID,
    team_id=APNS.TEAM_ID,
    topic=APNS.BUNDLE_ID,
    use_sandbox=APNS.SANDBOX,
)


async def send_push(device_id, message):
    request = NotificationRequest(
        device_token=device_id,
        message={
            "aps": {
                "alert": message
            }
        },
    )
    await apns_key_client.send_notification(request)
