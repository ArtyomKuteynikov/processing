from django import forms
from django_recaptcha.fields import ReCaptchaField
from currency.models import Links, PaymentMethods
from customer.models import Cards, CardsLimits, CustomerDocument, Websites, WebsitesCategories


class WebsitesForm(forms.ModelForm):
    class Meta:
        model = Websites
        fields = ['domain', 'description', 'category', 'payment_method', 'currency']

        widgets = {
            'description': forms.Textarea(attrs={'rows': 3})
        }


class CardsForm(forms.ModelForm):
    class Meta:
        model = Cards
        fields = ['name', 'method', 'payment_details', 'initials', 'status']


class KYCForm(forms.ModelForm):
    class Meta:
        model = CustomerDocument
        exclude = ['customer', 'status', 'created', 'updated']
        # fields = ['passport_number', 'authority', 'date_of_issue', 'date_of_birth', 'passport_scan_1', 'passport_scan_2', 'passport_video']
        widgets = {
            'date_of_issue': forms.DateInput(attrs={'type': 'date'}),
            'date_of_birth': forms.DateInput(attrs={'type': 'date'}),
        }


class LimitsForm(forms.ModelForm):
    class Meta:
        model = CardsLimits
        fields = ['input_min_limit', 'input_operation_limit', 'input_day_limit', 'input_month_limit', 'output_min_limit','output_operation_limit', 'output_dat_limit', 'output_month_limit']


class Step1Form(forms.Form):
    email = forms.EmailField(widget=forms.EmailInput(attrs={'placeholder': 'example@gmail.com'}), label='', )
    phone_number = forms.CharField(widget=forms.TextInput(attrs={'placeholder': '+79991234567'}), label='')
    # telegram_id = forms.CharField(widget=forms.TextInput(attrs={'placeholder': 'Telegram ID'}), label='')
    # captcha = ReCaptchaField(label='')


class Reset1Form(forms.Form):
    email = forms.EmailField(widget=forms.EmailInput(attrs={'placeholder': 'example@gmail.com'}), label='', )
    phone_number = forms.CharField(widget=forms.TextInput(attrs={'placeholder': '+79991234567'}), label='')
    # telegram_id = forms.CharField(widget=forms.TextInput(attrs={'placeholder': 'Telegram ID'}), label='')
    # captcha = ReCaptchaField(label='')


class Reset2Form(forms.Form):
    password = forms.CharField(widget=forms.PasswordInput(attrs={'placeholder': '••••••••'}), label='Пароль', )
    confirm_password = forms.CharField(widget=forms.PasswordInput(attrs={'placeholder': '••••••••'}), label='Подтвердить пароль', )


class LoginForm(forms.Form):
    email = forms.EmailField(widget=forms.EmailInput(attrs={'placeholder': 'example@gmail.com'}), label='', )
    password = forms.CharField(widget=forms.PasswordInput(attrs={'placeholder': '••••••••'}), label='', )
    # captcha = ReCaptchaField(label='')


class OTPForm(forms.Form):
    code = forms.IntegerField(widget=forms.NumberInput(attrs={'placeholder': '123456'}), label='', )


class RequestForm(forms.Form):
    CATEGORIES = [(i.id, i.__str__) for i in WebsitesCategories.objects.all()]
    email = forms.EmailField(widget=forms.EmailInput(attrs={'placeholder': 'example@gmail.com'}), label='Email', )
    phone_number = forms.CharField(widget=forms.TextInput(attrs={'placeholder': '+79991234567'}), label='Телефон')
    website = forms.CharField(widget=forms.TextInput(attrs={'placeholder': 'https://example.com'}), label='Сайт-площадка')
    comment = forms.ChoiceField(widget=forms.Select(attrs={'class': 'form-control'}), label='Категория', choices=CATEGORIES)
    # captcha = ReCaptchaField(label='')


class MerchantForm(forms.Form):
    email = forms.EmailField(widget=forms.EmailInput(attrs={'placeholder': 'example@gmail.com'}), label='', )
    phone_number = forms.CharField(widget=forms.TextInput(attrs={'placeholder': '+79991234567'}), label='')
    # telegram_id = forms.CharField(widget=forms.TextInput(attrs={'placeholder': 'Telegram ID'}), label='')
    invite_code = forms.CharField(widget=forms.TextInput(attrs={'placeholder': 'Инвайт код'}), label='')
    # captcha = ReCaptchaField(label='')


class SupportForm(forms.Form):
    title = forms.CharField(widget=forms.TextInput(attrs={'placeholder': 'Суть вашей проблемы'}), label='Тема')
    comment = forms.CharField(widget=forms.Textarea(attrs={'placeholder': 'подробно опишите проблему'}), label='Комментарий')
    file = forms.FileField(label='Файл')
    # captcha = ReCaptchaField(label='')


class SupportMessageForm(forms.Form):
    message = forms.CharField()
    file = forms.FileField()


class CustomerChangeForm(forms.Form):
    email = forms.EmailField()
    phone = forms.CharField()


class TelegramForm(forms.Form):
    telegram_id = forms.IntegerField()


class AccountSettings(forms.Form):
    time_zone = forms.IntegerField()


class WithdrawalForm(forms.Form):
    def __init__(self, *args, **kwargs):
        min_amount = kwargs.pop('min_amount', 0.01)
        max_amount = kwargs.pop('max_amount', 10000)

        super().__init__(*args, **kwargs)

        self.fields['amount'] = forms.FloatField(
            widget=forms.NumberInput(attrs={'placeholder': 'Сумма'}),
            label='Сумма',
            min_value=min_amount,
            max_value=max_amount
        )
    LINKS = [(i.id, i.__str__) for i in Links.objects.all()]
    # amount = forms.FloatField(widget=forms.NumberInput(attrs={'placeholder': 'Сумма'}), label='Сумма')
    link = forms.ChoiceField(widget=forms.Select(attrs={'class': 'form-control'}), label='Валюта', choices=LINKS)
    address = forms.CharField(widget=forms.TextInput(attrs={'placeholder': 'Адрес'}), label='Адрес')
    comment = forms.CharField(widget=forms.TextInput(attrs={'placeholder': 'Комментарий'}), label='Комментарий', required=False)


class ChoseMethodForm(forms.Form):
    METHODS = [(i.id, i.name) for i in PaymentMethods.objects.all()]
    method = forms.ChoiceField(widget=forms.Select(attrs={'class': 'form-control'}), label='Банк', choices=METHODS)
