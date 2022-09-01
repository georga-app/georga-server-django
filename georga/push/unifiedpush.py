import requests


def send_push(device_url: str, message: str):
    x = requests.post(device_url, data=message)
    return x.status_code


def send_push_mass(device_urls: [str], message: str):
    for device_url in device_urls:
        x = requests.post(device_url, data=message)
        return x.status_code
