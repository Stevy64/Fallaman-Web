#!/usr/bin/env python
"""Point d'entrée Django de Fallaman."""

import os
import sys


def main():
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings.development")
    try:
        from django.core.management import execute_from_command_line
    except ImportError as exc:
        raise ImportError(
            "Django n'est pas disponible. Activez le virtualenv et installez les dépendances."
        ) from exc
    execute_from_command_line(sys.argv)


if __name__ == "__main__":
    main()
