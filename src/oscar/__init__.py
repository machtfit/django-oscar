import os

# Use 'dev', 'beta', or 'final' as the 4th element to indicate release type.

VERSION = (1, 0, 1, 'machtfit', 76)


def get_short_version():
    return '%s.%s' % (VERSION[0], VERSION[1])


def get_version():
    return '{}.{}.{}-{}-{}'.format(*VERSION)


# Cheeky setting that allows each template to be accessible by two paths.
# Eg: the template 'oscar/templates/oscar/base.html' can be accessed via both
# 'base.html' and 'oscar/base.html'.  This allows Oscar's templates to be
# extended by templates with the same filename
OSCAR_MAIN_TEMPLATE_DIR = os.path.join(
    os.path.dirname(os.path.abspath(__file__)), 'templates/oscar')
