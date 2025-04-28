from django import forms
from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth.models import User
from .models import UserProfile, SellerVerification, USER_ROLES, PropertyImage, Property, CITIES


class UserSignupForm(UserCreationForm):
    email = forms.EmailField(required=True)
    role = forms.ChoiceField(choices=[choice for choice in USER_ROLES if choice[0] != 'admin'])

    class Meta:
        model = User
        fields = ('username', 'email', 'password1', 'password2')
        help_texts = {
            'username': None,
            'password1': None,
            'password2': None,
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Remove help texts from all fields
        for field in self.fields.values():
            field.help_text = None

    def save(self, commit=True):
        user = super().save(commit=False)
        user.email = self.cleaned_data['email']

        if commit:
            user.save()

        return user


class UserProfileForm(forms.ModelForm):
    class Meta:
        model = UserProfile
        fields = ('phone', 'address')


class SellerVerificationForm(forms.ModelForm):
    class Meta:
        model = SellerVerification
        fields = ('profile_picture', 'identity_proof')


class PropertyForm(forms.ModelForm):
    class Meta:
        model = Property
        fields = [
            'title', 'description', 'property_type', 'purpose',
            'price', 'area_size', 'bedrooms', 'bathrooms',
            'address', 'city'
        ]
        widgets = {
            'city': forms.Select(choices=CITIES)
        }

    def __init__(self, *args, **kwargs):
        self.seller = kwargs.pop('seller', None)
        super().__init__(*args, **kwargs)

    def save(self, commit=True):
        property_instance = super().save(commit=False)
        if self.seller:
            property_instance.seller = self.seller
        if commit:
            property_instance.save()
        return property_instance


class PropertyImageForm(forms.ModelForm):
    class Meta:
        model = PropertyImage
        fields = ['image', 'is_primary']
