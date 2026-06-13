from django import forms
from django.contrib.auth.forms import UserCreationForm, AuthenticationForm
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError

User = get_user_model()


class CustomUserCreationForm(UserCreationForm):
    """
    Форма регистрации нового пользователя
    """
    email = forms.EmailField(
        required=True,
        widget=forms.EmailInput(attrs={
            'class': 'auth-form-input',
            'placeholder': 'example@mail.com',
            'id': 'authRegEmail'
        })
    )
    password1 = forms.CharField(
        widget=forms.PasswordInput(attrs={
            'class': 'auth-form-input',
            'placeholder': 'Минимум 8 символов',
            'id': 'authRegPassword'
        })
    )
    password2 = forms.CharField(
        widget=forms.PasswordInput(attrs={
            'class': 'auth-form-input',
            'placeholder': 'Повторите пароль',
            'id': 'authRegConfirm'
        })
    )

    class Meta:
        model = User
        fields = ('email', 'password1', 'password2')

    def clean_email(self):
        """
        Проверка уникальности email
        """
        email = self.cleaned_data.get('email')
        if User.objects.filter(email=email).exists():
            raise ValidationError('Пользователь с таким email уже зарегистрирован')
        return email

    def save(self, commit=True):
        user = super().save(commit=False)
        # Генерируем username из email
        user.username = self.cleaned_data['email'].split('@')[0]
        user.email = self.cleaned_data['email']

        # Проверяем уникальность username
        base_username = user.username
        counter = 1
        while User.objects.filter(username=user.username).exists():
            user.username = f"{base_username}{counter}"
            counter += 1

        if commit:
            user.save()
        return user


class CustomAuthenticationForm(AuthenticationForm):
    """
    Форма входа пользователя
    """
    username = forms.CharField(
        widget=forms.TextInput(attrs={
            'class': 'auth-form-input',
            'placeholder': 'example@mail.com',
            'id': 'authEmail'
        })
    )
    password = forms.CharField(
        widget=forms.PasswordInput(attrs={
            'class': 'auth-form-input',
            'placeholder': 'Введите пароль',
            'id': 'authPassword'
        })
    )

    def clean_username(self):
        """
        Позволяет вводить email вместо username
        """
        username = self.cleaned_data.get('username')

        # Если введен email, ищем пользователя по email
        if '@' in username:
            try:
                user = User.objects.get(email=username)
                return user.username
            except User.DoesNotExist:
                pass
        return username


class PasswordResetForm(forms.Form):
    """
    Форма восстановления пароля
    """
    email = forms.EmailField(
        widget=forms.EmailInput(attrs={
            'class': 'auth-form-input',
            'placeholder': 'example@mail.com',
            'id': 'authResetEmail'
        })
    )

    def clean_email(self):
        """
        Проверяет существование пользователя с таким email
        """
        email = self.cleaned_data.get('email')
        if not User.objects.filter(email=email).exists():
            raise ValidationError('Пользователь с таким email не найден')
        return email


class ResendVerificationForm(forms.Form):
    """
    Форма повторной отправки письма подтверждения
    """
    email = forms.EmailField(
        required=False,
        widget=forms.EmailInput(attrs={
            'class': 'auth-form-input',
            'placeholder': 'example@mail.com',
            'id': 'resendEmail'
        })
    )