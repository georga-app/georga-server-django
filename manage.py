#!/usr/bin/env python
"""Django's command-line utility for administrative tasks."""
import os
import sys

import dotenv


def main():
    """Run administrative tasks."""
    dotenv.load_dotenv()
    os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'georga.settings')
    try:
        from django.core.management import execute_from_command_line
    except ImportError as exc:
        raise ImportError(
            "Couldn't import Django. Are you sure it's installed and "
            "available on your PYTHONPATH environment variable? Did you "
            "forget to activate a virtual environment?"
        ) from exc
    execute_from_command_line(sys.argv)


if __name__ == '__main__':

    # enable ptvsd debugging (needs open port 51000)
    if int(os.environ.get("DEBUG_PTVSD", 0)):
        try:
            if True:  # os.environ.get('RUN_MAIN') or os.environ.get('WERKZEUG_RUN_MAIN'):
                # import ptvsd
                # ptvsd.enable_attach(address=('0.0.0.0', 51000))
                # # uncomment these two lines, if you need to debug initialization code:
                # # ptvsd.wait_for_attach()
                # # ptvsd.break_into_debugger()
                # print("Attached remote debugger")
        except Exception as ex:
            if hasattr(ex, 'message'):
                print('ptvsd debugging not possible:' + ex.message)
            else:
                print('ptvsd debugging not possible:' + str(ex))

    # drop into pdb on error
    if int(os.environ.get("DEBUG_PDB", 0)):
        def info(type, value, tb):
            if hasattr(sys, 'ps1') or not sys.stderr.isatty():
                sys.__excepthook__(type, value, tb)
            else:
                import traceback
                import pdb
                traceback.print_exception(type, value, tb)
                print
                pdb.post_mortem(tb)
        sys.excepthook = info

    # start
    main()
