from firebase_admin import messaging


async def send_push(device_id: str, message_title: str, message_text: str):
    message = messaging.Message(
        notification={
            'title': message_title,
            'body': message_text
        },
        token=device_id,
    )
    response = messaging.send(message)
    return response


async def send_push_mass(device_ids: [str], message_title: str, message_text: str):
    message = messaging.MulticastMessage(
        notification={
            'title': message_title,
            'body': message_text
        },
        tokens=device_ids,
    )
    response = messaging.send_multicast(message)
    print('{0} messages were sent successfully'.format(response.success_count))
    return response
