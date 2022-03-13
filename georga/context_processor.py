from . import settings


def main(request):
    return {'GITHUB_URL': settings.REPOSITORY_URL}
