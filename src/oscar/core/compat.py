from django.conf import settings
from django.contrib.auth.models import User
from django.core.exceptions import ImproperlyConfigured

from oscar.core.loading import get_model


# A setting that can be used in foreign key declarations
AUTH_USER_MODEL = getattr(settings, 'AUTH_USER_MODEL', 'auth.User')
# Two additional settings that are useful in South migrations when
# specifying the user model in the FakeORM
try:
    AUTH_USER_APP_LABEL, AUTH_USER_MODEL_NAME = AUTH_USER_MODEL.rsplit('.', 1)
except ValueError:
    raise ImproperlyConfigured("AUTH_USER_MODEL must be of the form"
                               " 'app_label.model_name'")


def get_user_model():
    """
    Return the User model. Doesn't require the app cache to be fully
    initialised.

    This used to live in compat to support both Django 1.4's fixed User model
    and custom user models introduced thereafter.
    Support for Django 1.4 has since been dropped in Oscar, but our
    get_user_model remains because code relies on us annotating the _meta class
    with the additional fields, and other code might rely on it as well.
    """

    try:
        model = get_model(AUTH_USER_APP_LABEL, AUTH_USER_MODEL_NAME)
    except LookupError:
        # Convert exception to an ImproperlyConfigured exception for
        # backwards compatibility with previous Oscar versions and the
        # original get_user_model method in Django.
        raise ImproperlyConfigured(
            "AUTH_USER_MODEL refers to model '%s' that has not been installed"
            % settings.AUTH_USER_MODEL)

    # Test if user model has any custom fields and add attributes to the _meta
    # class
    core_fields = set([f.name for f in User._meta.fields])
    model_fields = set([f.name for f in model._meta.fields])
    new_fields = model_fields.difference(core_fields)
    model._meta.has_additional_fields = len(new_fields) > 0
    model._meta.additional_fields = new_fields

    return model


# Make backwards-compatible atomic decorator available
try:
    from django.db.transaction import atomic as atomic_compat
except ImportError:
    from django.db.transaction import commit_on_success as atomic_compat
atomic_compat = atomic_compat
