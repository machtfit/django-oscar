import string
import random

from django import forms
from django.core.exceptions import ValidationError
from django.utils.translation import ugettext_lazy as _
from django.utils.translation import pgettext_lazy

from oscar.core.loading import get_profile_class
from oscar.core.compat import get_user_model, existing_user_fields
from oscar.apps.customer.utils import normalise_email


User = get_user_model()


def generate_username():
    # Python 3 uses ascii_letters. If not available, fallback to letters
    try:
        letters = string.ascii_letters
    except AttributeError:
        letters = string.letters
    uname = ''.join([random.choice(letters + string.digits + '_')
                     for i in range(30)])
    try:
        User.objects.get(username=uname)
        return generate_username()
    except User.DoesNotExist:
        return uname


class OrderSearchForm(forms.Form):
    date_from = forms.DateField(
        required=False, label=pgettext_lazy("start date", "From"))
    date_to = forms.DateField(
        required=False, label=pgettext_lazy("end date", "To"))
    order_number = forms.CharField(required=False, label=_("Order number"))

    def clean(self):
        if self.is_valid() and not any([self.cleaned_data['date_from'],
                                        self.cleaned_data['date_to'],
                                        self.cleaned_data['order_number']]):
            raise forms.ValidationError(_("At least one field is required."))
        return super(OrderSearchForm, self).clean()

    def description(self):
        """
        Uses the form's data to build a useful description of what orders
        are listed.
        """
        if not self.is_bound or not self.is_valid():
            return _('All orders')
        else:
            date_from = self.cleaned_data['date_from']
            date_to = self.cleaned_data['date_to']
            order_number = self.cleaned_data['order_number']
            return self._orders_description(date_from, date_to, order_number)

    def _orders_description(self, date_from, date_to, order_number):
        if date_from and date_to:
            if order_number:
                desc = _('Orders placed between %(date_from)s and '
                         '%(date_to)s and order number containing '
                         '%(order_number)s')
            else:
                desc = _('Orders placed between %(date_from)s and '
                         '%(date_to)s')
        elif date_from:
            if order_number:
                desc = _('Orders placed since %(date_from)s and '
                         'order number containing %(order_number)s')
            else:
                desc = _('Orders placed since %(date_from)s')
        elif date_to:
            if order_number:
                desc = _('Orders placed until %(date_to)s and '
                         'order number containing %(order_number)s')
            else:
                desc = _('Orders placed until %(date_to)s')
        elif order_number:
            desc = _('Orders with order number containing %(order_number)s')
        else:
            return None
        params = {
            'date_from': date_from,
            'date_to': date_to,
            'order_number': order_number,
        }
        return desc % params

    def get_filters(self):
        date_from = self.cleaned_data['date_from']
        date_to = self.cleaned_data['date_to']
        order_number = self.cleaned_data['order_number']
        kwargs = {}
        if date_from and date_to:
            kwargs['date_placed__range'] = [date_from, date_to]
        elif date_from and not date_to:
            kwargs['date_placed__gt'] = date_from
        elif not date_from and date_to:
            kwargs['date_placed__lt'] = date_to
        if order_number:
            kwargs['number__contains'] = order_number
        return kwargs


class UserForm(forms.ModelForm):

    def __init__(self, user, *args, **kwargs):
        self.user = user
        kwargs['instance'] = user
        super(UserForm, self).__init__(*args, **kwargs)
        if 'email' in self.fields:
            self.fields['email'].required = True

    def clean_email(self):
        """
        Make sure that the email address is aways unique as it is
        used instead of the username. This is necessary because the
        unique-ness of email addresses is *not* enforced on the model
        level in ``django.contrib.auth.models.User``.
        """
        email = normalise_email(self.cleaned_data['email'])
        if User._default_manager.filter(
                email__iexact=email).exclude(id=self.user.id).exists():
            raise ValidationError(
                _("A user with this email address already exists"))
        # Save the email unaltered
        return email

    class Meta:
        model = User
        fields = existing_user_fields(['first_name', 'last_name', 'email'])


Profile = get_profile_class()
if Profile:  # noqa (too complex (12))

    class UserAndProfileForm(forms.ModelForm):

        def __init__(self, user, *args, **kwargs):
            try:
                instance = Profile.objects.get(user=user)
            except Profile.DoesNotExist:
                # User has no profile, try a blank one
                instance = Profile(user=user)
            kwargs['instance'] = instance

            super(UserAndProfileForm, self).__init__(*args, **kwargs)

            # Get profile field names to help with ordering later
            profile_field_names = list(self.fields.keys())

            # Get user field names (we look for core user fields first)
            core_field_names = set([f.name for f in User._meta.fields])
            user_field_names = ['email']
            for field_name in ('first_name', 'last_name'):
                if field_name in core_field_names:
                    user_field_names.append(field_name)
            user_field_names.extend(User._meta.additional_fields)

            # Store user fields so we know what to save later
            self.user_field_names = user_field_names

            # Add additional user form fields
            additional_fields = forms.fields_for_model(
                User, fields=user_field_names)
            self.fields.update(additional_fields)

            # Ensure email is required and initialised correctly
            self.fields['email'].required = True

            # Set initial values
            for field_name in user_field_names:
                self.fields[field_name].initial = getattr(user, field_name)

            # Ensure order of fields is email, user fields then profile fields
            self.fields.keyOrder = user_field_names + profile_field_names

        class Meta:
            model = Profile
            exclude = ('user',)

        def clean_email(self):
            email = normalise_email(self.cleaned_data['email'])

            users_with_email = User._default_manager.filter(
                email__iexact=email).exclude(id=self.instance.user.id)
            if users_with_email.exists():
                raise ValidationError(
                    _("A user with this email address already exists"))
            return email

        def save(self, *args, **kwargs):
            user = self.instance.user

            # Save user also
            for field_name in self.user_field_names:
                setattr(user, field_name, self.cleaned_data[field_name])
            user.save()

            return super(ProfileForm, self).save(*args, **kwargs)

    ProfileForm = UserAndProfileForm
else:
    ProfileForm = UserForm
