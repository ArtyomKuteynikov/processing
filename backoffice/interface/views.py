import codecs
import csv
import datetime
import time
import uuid
from functools import wraps
from itertools import groupby

from django.contrib.auth.decorators import login_required
from django.contrib.sessions.models import Session
from django.shortcuts import render, redirect, get_object_or_404
from django.urls import reverse
import pyotp
from .forms import Step1Form, LoginForm, OTPForm, Reset1Form, Reset2Form, RequestForm, MerchantForm, SupportForm, \
    SupportMessageForm, CustomerChangeForm, WithdrawalForm, CardsForm, LimitsForm, ChoseMethodForm, KYCForm, \
    WebsitesForm, TelegramForm, AccountSettings
from customer.models import Customer, Request, InviteCodes, Settings, User, TraderExchangeDirections, Cards, \
    CardsLimits, Notifications, CustomerDocument, Websites, WebsitesCategories
from order.models import Transaction, Order
from wallet.models import Balance, Withdrawal
from support.models import Ticket, FAQ, TicketMessage
from currency.models import Links, ExchangeDirection, PaymentMethods
import random
import redis
import qrcode
from interface.captcha import grecaptcha_verify
from django.contrib.auth import authenticate, login, logout
from django.http import JsonResponse, HttpResponseRedirect, HttpResponse
from django.core.cache import cache
from .utils import send_email, send_tg, handle_uploaded_file
from passlib.context import CryptContext
from PIL import Image
from io import BytesIO
import base64
from django.db.models import Q, Avg, Count, F

from currency.models import Currency, Networks

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

DEPOSIT_ADDRESS = "TVM7MvLEaD7GSWbgy4jkcLnFCXuEjF1RfJ"


def is_user_exists(email, phone):
    return Customer.objects.filter(email=email).exists() or \
        Customer.objects.filter(phone=phone).exists()


def step1(request):
    if request.method == 'POST':
        form = Step1Form(request.POST)
        exists = is_user_exists(form.data['email'], form.data['phone_number'])
        if exists:
            customer = Customer.objects.filter(Q(email=form.data['email']) | Q(phone=form.data['phone_number'])).first()
            send_reset_email(customer.email)
            key = str(uuid.uuid4())
            cache.set(f"otp:{key}", customer.email, timeout=600)
            return redirect(reverse('verify-email') + f'?session={key}')
        if form.is_valid() and not exists:
            customer = Customer.objects.create(
                username=form.data['email'],
                account_type='TRADER',
                account_status='active',
                status='NEW',
                email=form.data['email'],
                phone=form.data['phone_number'],
                key=str(uuid.uuid4()),
                lang_code='ru',
                time_zone=0,
                interest_rate=5
            )
            customer.save()
            currency = Currency.objects.get(ticker='USDT')
            network = Networks.objects.get(short_name='TRC20')
            link = Links.objects.get(currency=currency, network=network)
            wallet = Balance.objects.create(
                balance_link=link,
                account=customer,
                amount=0,
                frozen=0
            )
            wallet.save()
            return redirect(reverse('step2') + f'?customer={customer.key}')
    else:
        form = Step1Form()
    return render(request, 'auth/trader/trader-step-1.html', {'form': form})


def step2(request):
    customer = request.GET.get('customer', None)
    customer = Customer.objects.filter(key=customer).first()
    if not customer:
        return redirect('login')
    if customer.email_is_verified or customer.phone_is_verified:
        return redirect(reverse('step3') + f'?customer={customer.key}')
    if request.method == 'POST':
        email_code = cache.get(f"email:otp:{customer.email}")
        email_sent_code = request.POST.get('email-code')
        if str(email_code) == str(email_sent_code):
            cus = Customer.objects.get(id=customer.id)
            cus.email_is_verified = True
            cus.phone_is_verified = True
            cus.save()
            return redirect(reverse('step3') + f'?customer={customer.key}')
        else:
            return render(request, 'auth/trader/trader-step-2.html',
                          {'customer': customer.key, 'email': customer.email,
                           'error': 'Incorrect codes'})
    return render(request, 'auth/trader/trader-step-2.html',
                  {'customer': customer.key, 'email': customer.email})


def step3(request):
    customer = request.GET.get('customer', None)
    customer = Customer.objects.filter(key=customer).first()
    if not customer:
        return redirect('login')
    if customer.password:
        return redirect(reverse('step4') + f'?customer={customer.key}')
    if request.method == 'POST':
        password = request.POST.get('password')
        cus = Customer.objects.get(id=customer.id)
        cus.password = pwd_context.hash(password)
        cus.save()
        return redirect(reverse('step4') + f'?customer={customer.key}')
    return render(request, 'auth/trader/trader-step-3.html', {'customer': customer.key})


def step4(request):
    customer = request.GET.get('customer', None)
    customer = Customer.objects.filter(key=customer).first()
    if not customer:
        return redirect('login')
    if customer.value_2fa:
        return redirect('success')
    key = pyotp.random_base32()
    uri = pyotp.totp.TOTP(key).provisioning_uri(
        name=customer.email,
        issuer_name='Processing')
    qr_image_pil = qrcode.make(uri).get_image()
    stream = BytesIO()
    qr_image_pil.save(stream, format='PNG')
    qr_image_base64 = base64.b64encode(stream.getvalue()).decode('utf-8')
    cus = Customer.objects.get(id=customer.id)
    cus.method_2fa = 2
    cus.value_2fa = key
    cus.save()
    if request.method == 'POST':
        return redirect('success')
    return render(request, 'auth/trader/trader-step-4.html',
                  {'qr_image_base64': qr_image_base64, 'customer': customer.key})


def success(request):
    return render(request, 'auth/trader/success.html')


@login_required
def change_pas(request):
    key = str(uuid.uuid4())
    cache.set(f"otp:reset1:{key}", request.user.email, timeout=600)
    return redirect(reverse('reset2') + f'?session={key}')


def reset1(request):
    if request.method == 'POST':
        form = Reset1Form(request.POST)
        if (Customer.objects.filter(email=form.data['email']).exists() or
                Customer.objects.filter(phone=form.data['phone_number']).exists()):
            key = str(uuid.uuid4())
            cache.set(f"otp:reset1:{key}", form.data['email'], timeout=600)
            return redirect(reverse('reset2') + f'?session={key}')
    else:
        form = Reset1Form()
    return render(request, 'auth/password-reset/step1.html', {'form': form})


def reset2(request):
    key = request.GET.get('session', None)
    email = cache.get(f"otp:reset1:{key}")
    customer = Customer.objects.filter(email=email).first()
    if not customer:
        return redirect('login')
    if request.method == 'POST':
        email_code = cache.get(f"email:otp:{customer.email}")
        email_sent_code = request.POST.get('email-code')
        if str(email_code) == str(email_sent_code):
            cus = Customer.objects.get(id=customer.id)
            cus.email_is_verified = True
            cus.phone_is_verified = True
            cus.save()
            key = str(uuid.uuid4())
            cache.set(f"otp:reset2:{key}", customer.email, timeout=600)
            return redirect(reverse('reset3') + f'?session={key}')
        else:
            return render(request, 'auth/password-reset/step2.html',
                          {'session': key, 'email': customer.email,
                           'error': 'Incorrect codes'})
    return render(request, 'auth/password-reset/step2.html',
                  {'session': key, 'email': customer.email})


def reset3(request):
    key = request.GET.get('session', None)
    email = cache.get(f"otp:reset2:{key}")
    customer = Customer.objects.filter(email=email).first()
    print(customer)
    if not customer:
        return redirect('login')
    if request.method == 'POST':
        form = Reset2Form(request.POST)
        password = form.data.get('password')
        confirm_password = form.data.get('confirm_password')
        print(password, confirm_password)
        if password == confirm_password:
            cus = Customer.objects.get(id=customer.id)
            cus.password = pwd_context.hash(password)
            cus.save()
            msg_body = f'''
Уважаемый, клиент!
Вы успешно сбросили пароль своей учетной записи.
В целях безопасности снятие средств с вашего счета будет ограничено в течение следующих 24 часов.
Если вы не сбрасывали пароль, рекомендуем немедленно связаться с службой поддержки {"support@processing.com"}., используя зарегистрированный адрес электронной почты
'''
            send_email(email, 'Уведомление об изменении пароля', msg_body)
            cache.set(f'restriction:{email}', 1, timeout=86400)
            return redirect(reverse('login'))
        form.add_error(None, "Пароли не совпадают")
    else:
        form = Reset2Form()
    return render(request, 'auth/password-reset/step3.html', {'form': form, 'session': key})


def login_view(request):
    form = LoginForm()
    if request.method == 'POST':
        form = LoginForm(request.POST)
        if form.is_valid():
            email = form.data['email']
            retries = cache.get(f"retries:login:{email}") if cache.get(f"retries:login:{email}") else 0
            if retries >= 3:
                form.add_error(None, "Вы ввели неверный пароль 3 раза, попробуйте заново через 10 минут")
                return render(request, 'auth/login.html', {'form': form})
            password = form.data['password']
            print(request.META['REMOTE_ADDR'])
            user = Customer.objects.filter(email=email).first()
            if not user:
                form.add_error(None, "Такого пользователя не существует")
                return render(request, 'auth/login.html', {'form': form})
            if user.account_status == 'blocked':
                form.add_error(None, "Пользователь заблокирован")
                return render(request, 'auth/login.html', {'form': form})
            if not user.email_is_verified or not user.phone_is_verified:
                return redirect(reverse('step2') + f'?customer={user.key}')
            if not user.password:
                return redirect(reverse('step3') + f'?customer={user.key}')
            if pwd_context.verify(password, user.password):
                key = str(uuid.uuid4())
                cache.set(f"otp:{key}", email, timeout=600)
                if user.customer.method_2fa == 2:
                    return redirect(reverse('2fa') + f'?session={key}')
                else:
                    login(request, Customer.objects.get(id=user.id))
                    return HttpResponseRedirect(reverse('index'))
            cache.set(f"retries:login:{email}", retries + 1, timeout=600)
            if retries >= 2:
                text = '''Уважаемый клиент!
                Мы обнаружили что вы ввели неверный пароль 3 раза подряд. Вы сможете повторить вход через 10 минут. Если вы забыли пароль - восстаносите его по этой ссылке ....
                Если это были не вы - незамедлительно свяжитесь в техподдержкой!'''
                send_email(email, 'Блокировка на 10 минут', text)
                form.add_error(None, "Неверный логин или пароль, попробуйте заново через 10 минут")
                return render(request, 'auth/login.html', {'form': form})
            form.add_error(None, "Неверный логин или пароль. Попробуйте еще раз или восстановите пароль")
    return render(request, 'auth/login.html', {'form': form})


def verify_email(request):
    key = request.GET.get('session', None)
    email = cache.get(f"otp:{key}")
    customer = Customer.objects.filter(email=email).first()
    if not customer:
        return redirect('login')
    if request.method == 'POST':
        email_code = cache.get(f"email:otp:{customer.email}")
        email_sent_code = request.POST.get('email-code')
        if str(email_code) == str(email_sent_code):
            key = str(uuid.uuid4())
            cache.set(f"otp:{key}", customer.email, timeout=600)
            return redirect(reverse('2fa') + f'?session={key}')
    key = str(uuid.uuid4())
    cache.set(f"otp:{key}", customer.email, timeout=600)
    return render(request, 'auth/email_verify.html',
                  {'session': key, 'email': customer.email})


def login_2fa(request):
    key = request.GET.get('session', None)
    email = cache.get(f"otp:{key}")
    customer = Customer.objects.filter(email=email).first()
    if not customer:
        return redirect('login')
    if customer.method_2fa != 0 and not customer.value_2fa:
        return redirect(reverse('step4') + f'?customer={customer.key}')
    form = OTPForm()
    if request.method == 'POST':
        form = OTPForm(request.POST)
        if form.is_valid():
            code = form.data['code']
            totp = pyotp.TOTP(customer.value_2fa)
            retries = cache.get(f"retries:otp:{email}") if cache.get(f"retries:otp:{email}") else 0
            if retries >= 3:
                form.add_error(None, "Вы ввели неверный код 3 раза, попробуйте заново через 60 минут")
                return render(request, 'auth/login.html', {'form': form})
            if totp.verify(code):
                login(request, Customer.objects.get(id=customer.id))
                return HttpResponseRedirect(reverse('index'))
            cache.set(f"retries:otp:{email}", retries + 1, timeout=600)
            if retries >= 2:
                form.add_error(None, "Неверный код, попробуйте заново через 60 минут")
                return render(request, 'auth/login.html', {'form': form})
            form.add_error(None, "Неверный логин или пароль. Попробуйте еще раз или восстановите пароль")
    return render(request, 'auth/2fa.html', {'form': form, "session": key})


def merchant_request(request):
    if request.method == 'POST':
        form = RequestForm(request.POST)
        exists = is_user_exists(form.data['email'], form.data['phone_number'])
        if exists:
            form.add_error(None, 'Пользователь с такими учетными данными уже существует')
        if form.is_valid() and not exists:
            customer = Request.objects.create(
                email=form.data['email'],
                phone=form.data['phone_number'],
                site=form.data['website'],
                category_id=form.data['comment'],
                status=0
            )
            customer.save()
            form = RequestForm()
            return render(request, 'auth/merchant/request.html',
                          {'message': 'Запрос на добавление мерчанта успешно создан', 'form': form})
    else:
        form = RequestForm()
    return render(request, 'auth/merchant/request.html', {'form': form})


def merchant1(request):
    if request.method == 'POST':
        form = MerchantForm(request.POST)
        exists = is_user_exists(form.data['email'], form.data['phone_number'])
        invite_code = InviteCodes.objects.filter(email=form.data['email'], code=form.data['invite_code']).first()
        if invite_code:
            invite_code = invite_code.expiry.date() >= datetime.datetime.now().date()
        if not invite_code:
            form.add_error(None, 'Недействительный инвайт код')
            return render(request, 'auth/merchant/step1.html', {'form': form})
        invite_code = InviteCodes.objects.get(email=form.data['email'], code=form.data['invite_code'], status=0)
        invite_code.status = 1
        invite_code.save()
        if exists:
            customer = Customer.objects.filter(Q(email=form.data['email']) | Q(phone=form.data['phone_number'])).first()
            send_reset_email(customer.email)
            key = str(uuid.uuid4())
            cache.set(f"otp:{key}", customer.email, timeout=600)
            return redirect(reverse('verify-email') + f'?session={key}')
        if form.is_valid() and not exists:
            customer = Customer.objects.create(
                username=form.data['email'],
                account_type='MERCHANT',
                account_status='active',
                status='NEW',
                email=form.data['email'],
                phone=form.data['phone_number'],
                key=str(uuid.uuid4()),
                lang_code='ru',
                time_zone=0,
                interest_rate=5
            )
            customer.save()
            currency = Currency.objects.get(ticker='USDT')
            network = Networks.objects.get(short_name='TRC20')
            link = Links.objects.get(currency=currency, network=network)
            wallet = Balance.objects.create(
                balance_link=link,
                account=customer,
                amount=0,
                frozen=0
            )
            wallet.save()
            return redirect(reverse('step2') + f'?customer={customer.key}')
    else:
        form = MerchantForm()
    return render(request, 'auth/merchant/step1.html', {'form': form})


@login_required
def kyc(request):
    form = KYCForm()
    verification = CustomerDocument.objects.filter(customer=request.user.customer).first()
    if verification:
        form = KYCForm(instance=verification)
    if request.method == 'POST':
        if verification:
            form = KYCForm(request.POST, request.FILES, instance=verification)
        else:
            form = KYCForm(request.POST, request.FILES)
        verification = form.save(commit=False)
        verification.customer = request.user.customer
        verification.status = 'request'
        verification.save()
        return redirect('index')
    return render(request, 'auth/trader/kyc.html', {'form': form, 'kyc': True})


@login_required
def index(request):
    return redirect('transactions')


@login_required
def transactions_view(request):
    start = request.GET.get('date-start', (datetime.datetime.now() - datetime.timedelta(days=30)).strftime('%Y-%m-%d'))
    end = request.GET.get('date-finish', (datetime.datetime.now()).strftime('%Y-%m-%d'))
    start_date = datetime.datetime.strptime(start, '%Y-%m-%d')
    end_date = datetime.datetime.strptime(end, '%Y-%m-%d') + datetime.timedelta(days=1)
    balances = Balance.objects.filter(account=request.user).all()
    transactions = Transaction.objects.filter(
        (Q(sender=request.user) | Q(receiver=request.user)) & Q(created__range=[start_date, end_date])).all().order_by(
        '-created')
    sites = list(set([i.site.domain for i in transactions if i.site]))
    links = list(set([i.link.__str__() for i in transactions if i.link]))
    types = list(set([i.get_type_display() for i in transactions if i.type]))
    statuses = list(set([i.get_status_display() for i in transactions if i.status]))
    address = DEPOSIT_ADDRESS
    if Customer.objects.filter(user_ptr=request.user).first():
        max_amount = Settings.objects.first().trader_deposit_limit if request.user.customer.account_type == 'TRADER' else Settings.objects.first().merchant_deposit
    else:
        max_amount = 0
    currency = Currency.objects.get(ticker='USDT')
    network = Networks.objects.get(short_name='TRC20')
    link = Links.objects.get(currency=currency, network=network)
    try:
        if request.user.customer.account_type == 'TRADER':
            form = WithdrawalForm(min_amount=Settings.objects.first().min_limit,
                                  max_amount=(request.user.customer.balance_set.filter(
                                      balance_link=link).first().amount if request.user.customer.balance_set.filter(
                                      balance_link=link).first() else 0) / link.currency.denomination)
        else:
            form = WithdrawalForm(min_amount=Settings.objects.first().withdrawal_min,
                                  max_amount=(request.user.customer.balance_set.filter(
                                      balance_link=link).first().amount if request.user.customer.balance_set.filter(
                                      balance_link=link).first() else 0) / link.currency.denomination)
    except:
        form = WithdrawalForm()
    return render(request, 'accounts/transactions.html',
                  {'transactions': transactions, 'balances': balances, 'address': address, 'max_amount': max_amount,
                   'form': form, 'sites': sites, 'links': links, 'types': types, 'statuses': statuses, 'start': start,
                   'finish': end})


@login_required
def transactions_csv(request):
    start = request.GET.get('date-start', (datetime.datetime.now() - datetime.timedelta(days=30)).strftime('%Y-%m-%d'))
    end = request.GET.get('date-finish', (datetime.datetime.now()).strftime('%Y-%m-%d'))
    start_date = datetime.datetime.strptime(start, '%Y-%m-%d')
    end_date = datetime.datetime.strptime(end, '%Y-%m-%d') + datetime.timedelta(days=1)
    transactions = Transaction.objects.filter(
        (Q(sender=request.user) | Q(receiver=request.user)) & Q(created__range=[start_date, end_date])).all()

    # Prepare CSV response
    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = 'attachment; filename="transactions_report.csv"'
    response.write(codecs.BOM_UTF8.decode('utf-8'))
    writer = csv.writer(response)
    writer.writerow(['ID', 'Дата и время', 'Сайт', 'Сумма', 'Валюта', 'Тип транзакции', 'Статус', 'Описание'])

    for obj in transactions:
        writer.writerow(
            [obj.id, obj.created, obj.site.domain if obj.site else '', obj.amount / obj.link.currency.denomination,
             obj.link.__str__(),
             obj.get_type_display(), obj.get_status_display(), obj.category])

    return response


@login_required
def orders_view(request):
    start = request.GET.get('date-start', (datetime.datetime.now() - datetime.timedelta(days=30)).strftime('%Y-%m-%d'))
    end = request.GET.get('date-finish', (datetime.datetime.now()).strftime('%Y-%m-%d'))
    start_date = datetime.datetime.strptime(start, '%Y-%m-%d')
    end_date = datetime.datetime.strptime(end, '%Y-%m-%d') + datetime.timedelta(days=1)
    balances = Balance.objects.filter(account=request.user).all()
    orders = Order.objects.filter(
        (Q(sender=request.user) | Q(trader=request.user)) & Q(created__range=[start_date, end_date])).all().order_by(
        '-created')
    banks = list(set([i.input_link.method.name for i in orders if i.input_link]))
    cards = list(set([i.method.name for i in orders if i.method]))
    sites = list(set([i.order_site.domain for i in orders if i.order_site]))
    output_links = list(set([i.output_link.__str__() for i in orders if i.output_link]))
    statuses = list(set([i.get_status_display() for i in orders if i.status]))
    address = DEPOSIT_ADDRESS
    if Customer.objects.filter(user_ptr=request.user).first():
        max_amount = Settings.objects.first().trader_deposit_limit if request.user.customer.account_type == 'TRADER' else Settings.objects.first().merchant_deposit
    else:
        max_amount = 0
    currency = Currency.objects.get(ticker='USDT')
    network = Networks.objects.get(short_name='TRC20')
    link = Links.objects.get(currency=currency, network=network)
    try:
        if request.user.customer.account_type == 'TRADER':
            form = WithdrawalForm(min_amount=Settings.objects.first().min_limit,
                                  max_amount=(request.user.customer.balance_set.filter(
                                      balance_link=link).first().amount if request.user.customer.balance_set.filter(
                                      balance_link=link).first() else 0) / link.currency.denomination)
        else:
            form = WithdrawalForm(min_amount=Settings.objects.first().withdrawal_min,
                                  max_amount=(request.user.customer.balance_set.filter(
                                      balance_link=link).first().amount if request.user.customer.balance_set.filter(
                                      balance_link=link).first() else 0) / link.currency.denomination)
    except:
        form = WithdrawalForm()
    return render(request, 'accounts/orders.html',
                  {'orders': orders, 'start': start, 'finish': end, 'balances': balances, 'address': address,
                   'max_amount': max_amount, 'form': form, 'banks': banks, 'cards': cards, 'sites': sites,
                   'output_links': output_links, 'statuses': statuses})


@login_required
def orders_csv(request):
    start = request.GET.get('date-start', (datetime.datetime.now() - datetime.timedelta(days=30)).strftime('%Y-%m-%d'))
    end = request.GET.get('date-finish', (datetime.datetime.now()).strftime('%Y-%m-%d'))
    start_date = datetime.datetime.strptime(start, '%Y-%m-%d')
    end_date = datetime.datetime.strptime(end, '%Y-%m-%d') + datetime.timedelta(days=1)
    orders = Order.objects.filter(
        (Q(sender=request.user) | Q(trader=request.user)) & Q(created__range=[start_date, end_date])).all()

    # Prepare CSV response
    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = 'attachment; filename="orders_report.csv"'
    response.write(codecs.BOM_UTF8.decode('utf-8'))
    writer = csv.writer(response)
    if request.user.customer.account_type == "TRADER":
        writer.writerow(
            ['ID', 'Дата и время', 'Тип ордера', 'Входящая сумма', 'Банк', 'Карта', 'От кого', 'Исходящая сумма',
             'Валюта', 'Статус'])
    else:
        writer.writerow(
            ['ID', 'Дата и время', 'Тип ордера', 'Входящая сумма', 'Исходящая сумма', 'Валюта', 'Статус', 'Client ID',
             'External ID', 'Контакт клиента'])
    for obj in orders:
        writer.writerow([obj.id, obj.created, obj.side,
                         obj.input_amount / obj.input_link.currency.denomination if obj.input_link else 0,
                         obj.output_amount / obj.output_link.currency.denomination, obj.output_link.__str__(),
                         obj.get_status_display(), obj.client_id, obj.external_id, obj.client_contact])

    return response


def order_start(request, order_id):
    order = Order.objects.get(uuid=order_id)
    if not order:
        return render(request, 'payment/order-not-found.html')
    if order.status != 0:
        return redirect('order-pay', order_id=order_id)
    if request.method == 'POST':
        form = ChoseMethodForm(request.POST)
        method = form.data['method']
        if order.side == 'OUT':
            card_number = request.POST.get('card_number')
            initials = request.POST.get('initials')
            order.card_number = card_number
            order.initials = initials
            order.bank_id = method
        input_link = Links.objects.filter(currency=Currency.objects.get(ticker='RUB'), method_id=method).first()
        order.input_link = input_link
        direction = ExchangeDirection.objects.filter(input=order.output_link, output=input_link).first()
        if order.side == 'IN':
            traders = TraderExchangeDirections.objects.filter(direction=direction, input=True).all()
        else:
            traders = TraderExchangeDirections.objects.filter(direction=direction, output=True).all()
        traders = [i for i in traders if
                   i.trader.verification_status().lower() == 'verified' and i.trader.status.lower() == 'active' and i.trader.account_status.lower() == 'active' and (
                       Balance.objects.filter(account=i.trader,
                                              balance_link=order.output_link).first().amount if Balance.objects.filter(
                           account=i.trader, balance_link=order.output_link).first() else 0) > order.output_amount]
        # TODO: сделать так чтобы карты проверялись и выдавались только трейдеры с картами которые еще не певысили лимиты
        '''trader_cards = []
        for trader in traders:
            cards = Cards.objects.filter(customer=trader.trader, method_id=method).all()
            for card in cards:
                if order.side == 'IN':
                    day_amount = sum([i.input_amount for i in Order.objects.filter(method=card, side='IN', created__range=[datetime.datetime.now()-datetime.timedelta(days=1), datetime.datetime.now()]).all()])
                    month_amount = sum([i.input_amount for i in Order.objects.filter(method=card, side='IN', created__range=[datetime.datetime.now()-datetime.timedelta(days=30), datetime.datetime.now()]).all()])
                    if card.limits.input_min_limit < order.input_amount < card.limits.input_operation_limit and card.limits.input_day_limit > day_amount and card.limits.input_month_limit > month_amount:
                        trader_cards.append(card)
                else:
                    day_amount = sum([i.input_amount for i in Order.objects.filter(method=card, side='OUT', created__range=[datetime.datetime.now() - datetime.timedelta(days=1), datetime.datetime.now()]).all()])
                    month_amount = sum([i.input_amount for i in Order.objects.filter(method=card, side='OUT', created__range=[datetime.datetime.now() - datetime.timedelta(days=30), datetime.datetime.now()]).all()])
                    if card.limits.output_min_limit < order.input_amount < card.limits.output_operation_limit and card.limits.output_day_limit > day_amount and card.limits.output_month_limit > month_amount:
                        trader_cards.append(card)'''
        if not traders:
            order.status = 4
            order.save()
            if order.side == 'OUT':
                merchant_balance = Balance.objects.get(account=order.sender, balance_link=order.output_link)
                merchant_balance.amount = merchant_balance.amount + order.output_amount
                merchant_balance.frozen = merchant_balance.frozen - order.output_amount
                merchant_balance.save()
                transaction = Transaction.objects.get(other_id_1=order.id)
                transaction.status = 4
                transaction.finished = True
                transaction.save()
            return redirect('order-pay', order_id=order_id)
        trader = random.choice(traders)
        order.trader = trader.trader
        card = Cards.objects.filter(customer=trader.trader, method_id=method).all().order_by('last_used')[0]
        card.last_used = datetime.datetime.now()
        card.save()
        order.method = card
        order.status = 1
        order.save()
        if order.side == 'OUT':
            transaction = Transaction.objects.get(other_id_1=order.id)
            transaction.receiver = trader.trader
            transaction.save()
        notification = Notifications(
            customer=trader.trader,
            title=f"Ордер №{order.id}",
            body=f"Новый ордер на {'вывод' if order.side == 'OUT' else 'ввод'} валюты",
            link='/orders',
            category='order'
        )
        notification.save()
        try:
            send_tg(trader.trader.telegram_id, notification.body)
        except Exception as e:
            print(e)
        return redirect('order-pay', order_id=order_id)
    side = order.side
    methods = PaymentMethods.objects.all()
    amount = order.input_amount / 100
    form = ChoseMethodForm()
    return render(request, 'payment/popup-start.html',
                  {'methods': methods, 'amount': amount, 'form': form, 'order_id': order_id, 'side': side})


def order_view(request, order_id):
    try:
        TIME_LIMIT = Settings.objects.first().order_life * 60
        order = Order.objects.get(uuid=order_id)
        if TIME_LIMIT <= time.time() - order.created.timestamp():
            if (order.status in [0, 1] and order.side == 'IN') or (order.status in [0, 2] and order.side == 'OUT'):
                order.status = 5
                order.save()
                error_text = 'Ордер отменен'
                return render(request, 'payment/order-error.html', {'error_text': error_text, 'order_id': order_id})
            elif (order.status in [0, 1] and order.side == 'IN') or (order.status in [0, 2] and order.side == 'OUT'):
                order.status = 6
                order.save()
                trader = Customer.objects.get(id=order.trader_id)
                trader.status = 'Inactive'
                trader.save()
                error_text = 'Ордер отменен'
                return render(request, 'payment/order-error.html', {'error_text': error_text, 'order_id': order_id})
        if not order:
            return render(request, 'payment/order-not-found.html')
        if order.status == 0:
            return redirect('order-start', order_id=order_id)
        if order.status in [4, 5, 6, 7, 8, 9, 10, 12]:
            error_text = 'Ордер отменен'
            return render(request, 'payment/order-error.html', {'error_text': error_text, 'order_id': order_id})
        side = order.side
        status = order.status
        amount = order.input_amount / order.input_link.currency.denomination
        time_limit = TIME_LIMIT - (int(time.time()) - int(order.created.timestamp()))
        card_number = order.method.payment_details
        initials = order.method.initials
        bank = order.method.method.name
        minutes = time_limit // 60
        seconds = time_limit % 60
        if status in [1, 2] and side == "IN":
            return render(request, 'payment/popup-pay.html', {'amount': amount, 'time': time_limit,
                                                              'card_number': card_number, 'initials': initials,
                                                              'bank': bank, 'status': status, 'order_id': order_id,
                                                              'minutes': minutes, 'seconds': seconds})
        if status == 1:
            return render(request, 'payment/popup-wait.html', {'amount': amount, 'time': time_limit,
                                                               'minutes': minutes, 'seconds': seconds,
                                                               'order_id': order_id, 'status': status})
        if status == 2:
            key = pwd_context.hash(str(order.client_id))
            return render(request, 'payment/order-confirm.html', {'amount': amount, 'time': time_limit,
                                                                  'minutes': minutes, 'seconds': seconds,
                                                                  'order_id': order_id, 'status': status, 'key': key})
        if status in [3, 11]:
            return render(request, 'payment/order-success.html', {'order_id': order_id})
    except Exception as e:
        error_text = str(e)
        return render(request, 'payment/order-error.html', {'error_text': error_text, 'order_id': order_id})


def realise_crypro(request, order_id):
    order = Order.objects.get(uuid=order_id)
    if not order:
        return JsonResponse({'status': -1})
    key = request.GET.get('key')
    if pwd_context.verify(str(order.client_id), str(key)) and order.status == 2:
        order.status = 3
        order.save()
        transaction = Transaction.objects.get(other_id_1=order.id)
        transaction.status = 1
        transaction.finished = True
        transaction.save()
        merchant_balance = Balance.objects.get(account=order.sender, balance_link=order.output_link)
        trader_balance = Balance.objects.get(account=order.trader, balance_link=order.output_link)
        merchant_balance.frozen = merchant_balance.frozen - order.output_amount
        merchant_balance.amount = merchant_balance.amount - order.output_amount * order.trader.interest_rate / 100
        trader_balance.amount = trader_balance.amount + order.output_amount
        merchant_balance.save()
        trader_balance.save()
        transaction_commission = Transaction(
            sender_id=order.sender_id,
            receiver_id=order.sender_id,
            site_id=order.order_site_id,
            link_id=order.output_link_id,
            amount=order.output_amount * order.trader.interest_rate / 100,
            finished=True,
            type=6,
            status=1,
            counted='1',
            other_id_1=order.id,
            category='Комиссия',
            created=datetime.datetime.now(),
            updated=datetime.datetime.now(),
        )
        transaction_commission.save()
        notification = Notifications(
            customer=order.trader,
            title=f"Ордер №{order.id} выполнен",
            body=f"Ордер №{order.id} выполнен, средства переведены",
            link='/orders',
            category='order'
        )
        notification.save()
        try:
            send_tg(order.trader.telegram_id, notification.body)
        except Exception as e:
            print(e)
        notification = Notifications(
            customer=order.sender,
            title=f"Ордер №{order.id} выполнен",
            body=f"Ордер №{order.id} выполнен, средства переведены трейдеру",
            link='/orders',
            category='order'
        )
        notification.save()
        try:
            send_tg(order.sender.telegram_id, notification.body)
        except Exception as e:
            print(e)
        return JsonResponse({'status': order.status})
    return JsonResponse({'status': -1})


@login_required
def realise_crypro_trader(request, order_id):
    order = Order.objects.get(id=order_id)
    if not order:
        return JsonResponse({'status': -1})
    if order.trader == request.user.customer and order.status == 2:
        order.status = 3
        order.save()
        transaction = Transaction(
            sender=order.trader,
            receiver=order.sender,
            site=order.order_site,
            link=order.output_link,
            amount=order.output_amount,
            finished=True,
            type=4,
            status=1,
            counted='1',
            other_id_1=order.id,
            category='Ордер клиента',
            created=datetime.datetime.now(),
            updated=datetime.datetime.now(),
        )
        transaction.save()
        transaction_commission = Transaction(
            sender_id=order.sender_id,
            receiver_id=order.sender_id,
            site_id=order.order_site_id,
            link_id=order.output_link_id,
            amount=order.output_amount * order.trader.interest_rate / 100,
            finished=True,
            type=6,
            status=1,
            counted='1',
            other_id_1=order.id,
            category='Комиссия',
            created=datetime.datetime.now(),
            updated=datetime.datetime.now(),
        )
        transaction_commission.save()
        merchant_balance = Balance.objects.get(account=order.sender, balance_link=order.output_link)
        trader_balance = Balance.objects.get(account=order.trader, balance_link=order.output_link)
        merchant_balance.amount = merchant_balance.amount + order.output_amount - order.output_amount * order.trader.interest_rate / 100
        trader_balance.amount = trader_balance.amount - order.output_amount  # + order.output_amount*order.trader.interest_rate/100
        merchant_balance.save()
        trader_balance.save()
        notification = Notifications(
            customer=order.trader,
            title=f"Ордер №{order.id} выполнен",
            body=f"Ордер №{order.id} выполнен, средства переведены мерчанту",
            link='/orders',
            category='order'
        )
        notification.save()
        try:
            send_tg(order.trader.telegram_id, notification.body)
        except Exception as e:
            print(e)
        notification = Notifications(
            customer=order.sender,
            title=f"Ордер №{order.id} выполнен",
            body=f"Ордер №{order.id} выполнен, средства переведены",
            link='/orders',
            category='order'
        )
        notification.save()
        try:
            send_tg(order.sender.telegram_id, notification.body)
        except Exception as e:
            print(e)
        return JsonResponse({'status': order.status})
    return JsonResponse({'status': -1})


def order_payed(request, order_id):
    try:
        order_id = int(order_id)
    except:
        pass
    if type(order_id) == int:
        order = Order.objects.get(Q(id=order_id))
    else:
        order = Order.objects.get(Q(uuid=order_id))
    if not order:
        return JsonResponse({'status': -1})
    order.status = 2
    order.save()
    if type(order_id) == str:
        notification = Notifications(
            customer=order.trader,
            title=f"Ордер №{order.id} средства переведены",
            body=f"Ордер №{order.id} клиент изменил статус на Средства переведены",
            link='/orders',
            category='order'
        )
        notification.save()
        try:
            send_tg(order.trader.telegram_id, notification.body)
        except Exception as e:
            print(e)
    return JsonResponse({'status': order.status})


def order_incorrect(request, order_id):
    try:
        order_id = int(order_id)
    except:
        pass
    if type(order_id) == int:
        order = Order.objects.get(Q(id=order_id))
    else:
        order = Order.objects.get(Q(uuid=order_id))
    if not order:
        return JsonResponse({'status': -1})
    order.status = 8
    order.save()
    if type(order_id) == str:
        notification = Notifications(
            customer=order.trader,
            title=f"Ордер №{order.id} неверная оплата",
            body=f"Ордер №{order.id} клиент изменил статус на Средства не переведены или неверная сумма",
            link='/orders',
            category='order'
        )
        notification.save()
        try:
            send_tg(order.trader.telegram_id, notification.body)
        except Exception as e:
            print(e)
    return JsonResponse({'status': order.status})


def order_cancel(request, order_id):
    order = Order.objects.get(uuid=order_id)
    if not order:
        return JsonResponse({'status': -1})
    order.status = 7
    order.save()
    notification = Notifications(
        customer=order.trader,
        title=f"Ордер №{order.id} отменен",
        body=f"Ордер №{order.id} клиент отменил ордер",
        link='/orders',
        category='order'
    )
    notification.save()
    try:
        send_tg(order.trader.telegram_id, notification.body)
    except:
        pass
    return JsonResponse({'status': order.status})


def order_cancel_trader(request, order_id):
    order = Order.objects.get(id=order_id)
    if not order:
        return JsonResponse({'status': -1})
    order.status = 4
    order.save()
    return JsonResponse({'status': order.status})


@login_required
def trader_active(request):
    customer = Customer.objects.get(id=request.user.customer.id)
    if not customer:
        return JsonResponse({'status': -1})
    customer.status = "ACTIVE"
    customer.save()
    return JsonResponse({'status': customer.status})


@login_required
def trader_inactive(request):
    customer = Customer.objects.get(id=request.user.customer.id)
    if not customer:
        return JsonResponse({'status': -1})
    customer.status = "Inactive"
    customer.save()
    return JsonResponse({'status': customer.status})


def order_status(request, order_id):
    order = Order.objects.get(uuid=order_id)
    if not order:
        return JsonResponse({'status': -1})
    return JsonResponse({'status': order.status})


@login_required
def withdrawals_view(request):
    start = request.GET.get('date-start', (datetime.datetime.now() - datetime.timedelta(days=30)).strftime('%Y-%m-%d'))
    end = request.GET.get('date-finish', (datetime.datetime.now()).strftime('%Y-%m-%d'))
    start_date = datetime.datetime.strptime(start, '%Y-%m-%d')
    end_date = datetime.datetime.strptime(end, '%Y-%m-%d') + datetime.timedelta(days=1)
    balances = Balance.objects.filter(account=request.user).all()
    withdrawals = Withdrawal.objects.filter(customer=request.user, created__range=[start_date, end_date]).all()
    address = DEPOSIT_ADDRESS
    if Customer.objects.filter(user_ptr=request.user).first():
        max_amount = Settings.objects.first().trader_deposit_limit if request.user.customer.account_type == 'TRADER' else Settings.objects.first().merchant_deposit
    else:
        max_amount = 0
    currency = Currency.objects.get(ticker='USDT')
    network = Networks.objects.get(short_name='TRC20')
    link = Links.objects.get(currency=currency, network=network)
    try:
        if request.user.customer.account_type == 'TRADER':
            form = WithdrawalForm(min_amount=Settings.objects.first().min_limit,
                                  max_amount=(request.user.customer.balance_set.filter(
                                      balance_link=link).first().amount if request.user.customer.balance_set.filter(
                                      balance_link=link).first() else 0) / link.currency.denomination)
        else:
            form = WithdrawalForm(min_amount=Settings.objects.first().withdrawal_min,
                                  max_amount=(request.user.customer.balance_set.filter(
                                      balance_link=link).first().amount if request.user.customer.balance_set.filter(
                                      balance_link=link).first() else 0) / link.currency.denomination)
    except:
        form = WithdrawalForm()
    return render(request, 'accounts/withdrawals.html',
                  {'withdrawals': withdrawals[::-1], 'balances': balances, 'address': address, 'max_amount': max_amount,
                   'form': form, 'start': start, 'finish': end})


@login_required
def withdrawal_csv(request):
    start = request.GET.get('date-start', (datetime.datetime.now() - datetime.timedelta(days=30)).strftime('%Y-%m-%d'))
    end = request.GET.get('date-finish', (datetime.datetime.now()).strftime('%Y-%m-%d'))
    start_date = datetime.datetime.strptime(start, '%Y-%m-%d')
    end_date = datetime.datetime.strptime(end, '%Y-%m-%d') + datetime.timedelta(days=1)
    withdrawals = Withdrawal.objects.filter(customer=request.user.customer, created__range=[start_date, end_date]).all()
    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = 'attachment; filename="withdrawals_report.csv"'
    response.write(codecs.BOM_UTF8.decode('utf-8'))
    writer = csv.writer(response)
    writer.writerow(['ID', 'Дата и время', 'Сумма', 'Адрес', 'Статус', 'Описание'])

    for obj in withdrawals:
        writer.writerow(
            [obj.id, obj.created, obj.amount / obj.currency.currency.denomination if obj.currency else 0, obj.address,
             obj.get_status_display(), obj.comment])

    return response


@login_required
def statistics(request):
    start = request.GET.get('date-start', (datetime.datetime.now() - datetime.timedelta(days=30)).strftime('%Y-%m-%d'))
    end = request.GET.get('date-finish', (datetime.datetime.now()).strftime('%Y-%m-%d'))
    aggregation_param = request.GET.get('groupby', 'days')
    start_date = datetime.datetime.strptime(start, '%Y-%m-%d')
    end_date = datetime.datetime.strptime(end, '%Y-%m-%d') + datetime.timedelta(days=1)
    transactions = Transaction.objects.filter(
        Q(sender=request.user) | Q(receiver=request.user) & Q(created__range=[start_date, end_date]))
    orders = Order.objects.filter(
        Q(sender=request.user) | Q(trader=request.user) & Q(created__range=[start_date, end_date]))
    if aggregation_param == 'days':
        transactions_aggregated = transactions.extra({'day': 'date(created)'}).values('day').annotate(
            total_transactions=Count('id'),
            successful_transactions=Count('id', filter=Q(status=2)),
            unsuccessful_transactions=Count('id', filter=Q(status=2, _negated=True)),
        )
        orders_aggregated = orders.extra({'day': 'date(created)'}).values('day').annotate(
            total_orders=Count('id'),
            successful_orders=Count('id', filter=Q(status=3)),
            unsuccessful_orders=Count('id', filter=Q(status=3, _negated=True)),
            avg_order_amount=Avg('output_amount') / 100
        )
        merged_data = []
        for key, group in groupby(
                sorted(list(transactions_aggregated) + list(orders_aggregated), key=lambda x: x['day']),
                key=lambda x: x['day']):
            combined_dict = {'param': key}
            for item in group:
                combined_dict.update(item)
            merged_data.append(combined_dict)
    elif aggregation_param == 'cards':
        orders_aggregated = orders.filter(trader=request.user.customer, side='IN').extra({'card': 'method_id'}).values(
            'card').annotate(
            total_orders=Count('id'),
            successful_orders=Count('id', filter=Q(status=3)),
            unsuccessful_orders=Count('id', filter=Q(status=3, _negated=True)),
            avg_order_amount=Avg('output_amount') / 100
        )
        merged_data = []
        for key, group in groupby(sorted(list(orders_aggregated), key=lambda x: str(x['card'])),
                                  key=lambda x: x['card']):
            if Cards.objects.filter(id=key).first():
                combined_dict = {'param': Cards.objects.filter(id=key).first().name}
                for item in group:
                    combined_dict.update(item)
                merged_data.append(combined_dict)
    elif aggregation_param == 'sites':
        transactions_aggregated = transactions.extra({'site': 'site_id'}).values('site').annotate(
            total_transactions=Count('id'),
            successful_transactions=Count('id', filter=Q(status=2)),
            unsuccessful_transactions=Count('id', filter=Q(status=2, _negated=True)),
        )
        orders_aggregated = orders.extra({'site': 'order_site_id'}).values('site').annotate(
            total_orders=Count('id'),
            successful_orders=Count('id', filter=Q(status=3)),
            unsuccessful_orders=Count('id', filter=Q(status=3, _negated=True)),
            avg_order_amount=Avg('output_amount') / 100
        )
        merged_data = []
        for key, group in groupby(
                sorted(list(transactions_aggregated) + list(orders_aggregated), key=lambda x: str(x['site'])),
                key=lambda x: str(x['site'])):
            if key and key != 'None':
                if Websites.objects.filter(id=key).first():
                    combined_dict = {'param': Websites.objects.filter(id=key).first().domain}
                    for item in group:
                        combined_dict.update(item)
                    merged_data.append(combined_dict)
    else:
        merged_data = 0
    return render(request, 'accounts/statistics.html',
                  {'groupby': aggregation_param, 'start': start, 'finish': end, 'data': merged_data})


@login_required
def statistics_csv(request):
    start = request.GET.get('date-start', (datetime.datetime.now() - datetime.timedelta(days=30)).strftime('%Y-%m-%d'))
    end = request.GET.get('date-finish', (datetime.datetime.now()).strftime('%Y-%m-%d'))
    aggregation_param = request.GET.get('groupby', 'days')
    start_date = datetime.datetime.strptime(start, '%Y-%m-%d')
    end_date = datetime.datetime.strptime(end, '%Y-%m-%d') + datetime.timedelta(days=1)
    transactions = Transaction.objects.filter(
        Q(sender=request.user) | Q(receiver=request.user) & Q(created__range=[start_date, end_date]))
    orders = Order.objects.filter(
        Q(sender=request.user) | Q(trader=request.user) & Q(created__range=[start_date, end_date]))
    if aggregation_param == 'days':
        transactions_aggregated = transactions.extra({'day': 'date(created)'}).values('day').annotate(
            total_transactions=Count('id'),
            successful_transactions=Count('id', filter=Q(status=2)),
            unsuccessful_transactions=Count('id', filter=Q(status=2, _negated=True)),
        )
        orders_aggregated = orders.extra({'day': 'date(created)'}).values('day').annotate(
            total_orders=Count('id'),
            successful_orders=Count('id', filter=Q(status=3)),
            unsuccessful_orders=Count('id', filter=Q(status=3, _negated=True)),
            avg_order_amount=Avg('output_amount') / 100
        )
        merged_data = []
        for key, group in groupby(
                sorted(list(transactions_aggregated) + list(orders_aggregated), key=lambda x: x['day']),
                key=lambda x: x['day']):
            combined_dict = {'param': key}
            for item in group:
                combined_dict.update(item)
            merged_data.append(combined_dict)
    elif aggregation_param == 'cards':
        orders_aggregated = orders.filter(trader=request.user.customer, side='IN').extra({'card': 'method_id'}).values(
            'card').annotate(
            total_orders=Count('id'),
            successful_orders=Count('id', filter=Q(status=3)),
            unsuccessful_orders=Count('id', filter=Q(status=3, _negated=True)),
            avg_order_amount=Avg('output_amount') / 100
        )
        merged_data = []
        for key, group in groupby(sorted(list(orders_aggregated), key=lambda x: str(x['card'])),
                                  key=lambda x: x['card']):
            if Cards.objects.filter(id=key).first():
                combined_dict = {'param': Cards.objects.filter(id=key).first().name}
                for item in group:
                    combined_dict.update(item)
                merged_data.append(combined_dict)
    elif aggregation_param == 'sites':
        transactions_aggregated = transactions.extra({'site': 'site_id'}).values('site').annotate(
            total_transactions=Count('id'),
            successful_transactions=Count('id', filter=Q(status=2)),
            unsuccessful_transactions=Count('id', filter=Q(status=2, _negated=True)),
        )
        orders_aggregated = orders.extra({'site': 'order_site_id'}).values('site').annotate(
            total_orders=Count('id'),
            successful_orders=Count('id', filter=Q(status=3)),
            unsuccessful_orders=Count('id', filter=Q(status=3, _negated=True)),
            avg_order_amount=Avg('output_amount') / 100
        )
        merged_data = []
        for key, group in groupby(
                sorted(list(transactions_aggregated) + list(orders_aggregated), key=lambda x: str(x['site'])),
                key=lambda x: str(x['site'])):
            if key and key != 'None':
                if Websites.objects.filter(id=key).first():
                    combined_dict = {'param': Websites.objects.filter(id=key).first().domain}
                    for item in group:
                        combined_dict.update(item)
                    merged_data.append(combined_dict)
    else:
        merged_data = []
    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = 'attachment; filename="statistics_report.csv"'

    response.write(codecs.BOM_UTF8.decode('utf-8'))
    writer = csv.writer(response)
    writer.writerow(['День' if groupby == 'days' else 'Площадка' if groupby == 'sites' else 'Карта', 'Всего ордеров',
                     'Успешных ордеров', 'Неуспешных ордеров', 'Всего ордеров', 'Успешных ордеров',
                     'Неуспешных ордеров', 'Соотношение ордеров к транзакциям(%)', 'Средний чек ордера'])

    for obj in merged_data:
        writer.writerow([
            obj['param'] if 'param' in obj else '',
            obj['total_transactions'] if 'total_transactions' in obj else 0,
            obj['successful_transactions'] if 'successful_transactions' in obj else 0,
            obj['unsuccessful_transactions'] if 'unsuccessful_transactions' in obj else 0,
            obj['total_orders'] if 'total_orders' in obj else 0,
            obj['unsuccessful_orders'] if 'unsuccessful_orders' in obj else 0,
            obj['unsuccessful_orders'] if 'unsuccessful_orders' in obj else 0,
            round(obj['total_orders'] / obj['total_transactions'] * 100, 2) if 'total_transactions' in obj and 'total_orders' in obj else 0,
            obj['avg_order_amount'] if 'avg_order_amount' in obj else 0
        ])

    return response


@login_required
def cards(request):
    cards = Cards.objects.filter(customer=request.user).all()
    if request.method == 'POST':
        form = CardsForm(request.POST)
        card = Cards(
            name=form.data['name'],
            method_id=form.data['method'],
            currency=Currency.objects.filter(ticker="RUB").first(),
            customer=request.user.customer,
            payment_details=form.data['payment_details'],
            initials=form.data['initials'],
            status=False
        )
        card.save()
        limits = CardsLimits(
            card=card,
            input_min_limit=0,
            input_operation_limit=0,
            input_day_limit=0,
            input_month_limit=0,
            output_min_limit=0,
            output_operation_limit=0,
            output_dat_limit=0,
            output_month_limit=0,
        )
        limits.save()
    form = CardsForm()
    limits_form = LimitsForm()
    return render(request, 'accounts/cards.html', {'cards': cards, 'form': form, 'limits': limits_form})


def card(request, card_id):
    card = get_object_or_404(Cards, pk=card_id)
    limits = get_object_or_404(CardsLimits, card=card)
    card_form = CardsForm(instance=card)
    limits_form = LimitsForm(instance=limits)
    if request.method == 'POST':
        card_form = CardsForm(request.POST, instance=card)
        limits_form = LimitsForm(request.POST, instance=limits)
        if card_form.is_valid() and limits_form.is_valid():
            card_form.save()
            limits_form.save()
            return redirect('cards')
    return render(request, 'accounts/card.html',
                  {'card': card, 'limits': limits, 'form': card_form, 'limits_form': limits_form,
                   'card_id': card_id})


@login_required
def settings(request):
    if request.method == 'POST':
        form = CustomerChangeForm(request.POST)
        customer = Customer.objects.get(id=request.user.id)
        if (Customer.objects.filter(email=form.data['email']).first() and Customer.objects.filter(
                email=form.data['email']).first() != request.user.customer) or (
                Customer.objects.filter(phone=form.data['phone']).first() and Customer.objects.filter(
                phone=form.data['phone']).first() != request.user.customer):
            form.add_error(None, 'Такой email или номер телефона уже зарегистрирован')
        if form.is_valid():
            customer.email = form.data['email']
            customer.phone = form.data['phone']
            # customer.telegram_id = form.data['telegram_id']
            customer.save()
        cache.set(f'restriction:{request.user.email}', 1, timeout=86400)
    return render(request, 'accounts/settings.html')


@login_required
def subscribe(request):
    if request.method == 'POST':
        form = TelegramForm(request.POST)
        customer = Customer.objects.get(id=request.user.id)
        if form.is_valid():
            customer.telegram_id = form.data['telegram_id']
            customer.save()
    return render(request, 'accounts/settings.html')


@login_required
def account_settings(request):
    if request.method == 'POST':
        form = AccountSettings(request.POST)
        customer = Customer.objects.get(id=request.user.id)
        if form.is_valid():
            customer.time_zone = form.data['time_zone']
            customer.save()
    return render(request, 'accounts/settings.html')


@login_required
def deposit(request):
    if request.method == 'POST':
        form = request.POST
        currency = Currency.objects.get(ticker='USDT')
        network = Networks.objects.get(short_name='TRC20')
        link = Links.objects.get(currency=currency, network=network)
        transaction = Transaction(
            sender=request.user.customer,
            receiver=request.user.customer,
            link=link,
            amount=float(form['amount']) * link.currency.denomination,
            finished=False,
            type=0,
            status=0,
            counted=1,
        )
        transaction.save()
        transaction.category = f"Пополнение аккаунта #{transaction.id}"
        transaction.save()
    return redirect('transactions')


@login_required
def withdrawals(request):
    if request.method == 'POST':
        form = WithdrawalForm(request.POST)
        withdrawal = Withdrawal(
            customer=request.user.customer,
            amount=float(form.data['amount']) * Links.objects.filter(
                id=form.data['link']).first().currency.denomination,
            currency_id=form.data['link'],
            address=form.data['address'],
            comment=form.data['comment'],
            status='NEW'
        )
        withdrawal.save()
    return redirect('withdrawals')


@login_required
def websites(request):
    websites = request.user.customer.websites_set.all()
    if request.method == 'POST':
        form = WebsitesForm(request.POST)
        website = form.save(commit=False)
        website.merchant = request.user.customer
        website.save()
    form = WebsitesForm()
    return render(request, 'accounts/platforms.html', {'websites': websites, 'form': form})


@login_required
def change_key(request, site):
    site = Websites.objects.get(id=site)
    if site.merchant == request.user.customer:
        site.key = uuid.uuid4()
        site.save()
    return redirect('website', website_id=site.id)


@login_required
def website(request, website_id):
    website = Websites.objects.get(id=website_id)
    categories = WebsitesCategories.objects.all()
    currencies = Currency.objects.all()
    if request.method == 'POST':
        form = WebsitesForm(request.POST, instance=website)
        website = form.save()
        website.save()
    return render(request, 'accounts/platform.html', {'website': website, 'categories': categories,
                                                      'currencies': currencies, 'website_id': website_id})


@login_required
def payment_methods(request):
    payment_methods = ExchangeDirection.objects.all()
    links = set([Links.objects.filter(method=i.method, currency=i.currency).first() for i in
                 Cards.objects.filter(customer=request.user.customer).all()])
    crypto = list(set([i.input.__str__() for i in payment_methods]))
    fiat = [i.__str__() for i in links]
    inputs = dict()
    outputs = dict()
    for i in [i.output for i in payment_methods]:
        temp_in = dict()
        temp_out = dict()
        for j in [i.input for i in payment_methods]:
            direction = ExchangeDirection.objects.filter(input=j, output=i).first()
            directions = TraderExchangeDirections.objects.filter(trader=request.user, direction=direction).first()
            if not direction:
                temp_in.update({j.__str__(): 'disabled'})
                temp_out.update({j.__str__(): 'disabled'})
                continue
            if not directions:
                temp_in.update({j.__str__(): ''})
                temp_out.update({j.__str__(): ''})
                continue
            if directions.input:
                temp_in.update({j.__str__(): 'checked'})
            else:
                temp_in.update({j.__str__(): ''})
            if directions.output:
                temp_out.update({j.__str__(): 'checked'})
            else:
                temp_out.update({j.__str__(): ''})
        inputs.update({i.__str__(): temp_in})
        outputs.update({i.__str__(): temp_out})
    return render(request, 'accounts/directions.html',
                  {'crypto': crypto, 'fiat': fiat, 'inputs': inputs, 'outputs': outputs})


@login_required
def update_direction(request):
    if request.method == 'POST':
        side = request.POST.get('side')
        input_name = request.POST.get('input')
        output_name = request.POST.get('output')
        is_checked = True if str(request.POST.get('isChecked')) == "true" else False
        print(bool(is_checked))
        currency = Currency.objects.filter(ticker=input_name.split('_')[0]).first()
        network = Networks.objects.filter(short_name=input_name.split('_')[1]).first()
        method = PaymentMethods.objects.filter(short_name=input_name.split('_')[1]).first()
        input_link = Links.objects.filter(currency=currency,
                                          network=network).first() if network else Links.objects.filter(
            currency=currency, method=method).first()
        currency = Currency.objects.filter(ticker=output_name.split('_')[0]).first()
        network = Networks.objects.filter(short_name=output_name.split('_')[1]).first()
        method = PaymentMethods.objects.filter(short_name=output_name.split('_')[1]).first()
        output_link = Links.objects.filter(
            Q(currency=currency) & Q(network=network)).first() if network else Links.objects.filter(
            Q(currency=currency) & Q(method=method)).first()
        exchange_direction = ExchangeDirection.objects.get(input=input_link, output=output_link)
        direction, created = TraderExchangeDirections.objects.get_or_create(
            trader=request.user.customer,
            direction=exchange_direction,
            defaults={'input': False, 'output': False}
        )
        if side == "IN":
            direction.input = bool(is_checked)
        elif side == "OUT":
            direction.output = bool(is_checked)
        direction.save()
        return JsonResponse({'status': 'success'})
    return JsonResponse({'status': 'error'})


@login_required
def disable_2fa(request):
    if request.method == 'POST':
        code = request.POST.get('code')
        if str(code) == str(cache.get(f"email:otp:{request.user.customer.email}")):
            customer = Customer.objects.get(id=request.user.id)
            customer.method_2fa = 0
            customer.save()
        return redirect('settings')
    else:
        code = random.randint(100000, 999999)
        print(code)
        cache.set(f"email:otp:{request.user.customer.email}", code, timeout=600)
        msg_body = f'''
                Здравствуйте!
                Мы получили запрос на отключение 2FA.
                Если это были не вы, проверьте безопасность своей учетной записи или смените пароль
    
                Код отключения 2FA: {code}'''
        send_email(request.user.customer.email, 'Предупреждение о попытке отключения 2FA', msg_body)
    return JsonResponse({'status': True})


@login_required
def enable_2fa(request):
    customer = Customer.objects.get(id=request.user.id)
    customer.method_2fa = 2
    customer.save()
    return JsonResponse({'status': True})


@login_required
def support(request):
    if request.method == 'POST':
        form = SupportForm(request.POST, request.FILES)
        new_ticket = Ticket(
            title=form.data['title'],
            priority=1,
            client=request.user.customer,
            status=0
        )
        new_ticket.save()
        message = TicketMessage(
            message=form.data['comment'],
            author=0,
            ticket=new_ticket,
            attachment=request.FILES['file'] if 'file' in request.FILES else '',
            read=0
        )
        message.save()
    tickets = Ticket.objects.filter(client=request.user).all()
    faq = FAQ.objects.all()
    form = SupportForm()
    return render(request, 'accounts/support.html', {'tickets': tickets, 'faq': faq, 'form': form})


@login_required
def complaint(request, order_id):
    form = SupportForm()
    form.initial['title'] = f"Вопрос по ордеру №{order_id}"
    if request.method == 'POST':
        form = SupportForm(request.POST, request.FILES)
        new_ticket = Ticket(
            title=form.data['title'],
            priority=0,
            client=request.user.customer,
            status=0
        )
        new_ticket.save()
        message = TicketMessage(
            message=form.data['comment'],
            author=0,
            ticket=new_ticket,
            attachment=request.FILES['file'] if 'file' in request.FILES else '',
            read=0
        )
        message.save()
        order = Order.objects.get(id=order_id)
        order.status = 10
        order.save()
        return redirect('support')
    return render(request, 'accounts/complaint.html', {'form': form, 'order_id': order_id})


@login_required
def ticket(request, ticket_id):
    if request.method == 'POST':
        form = SupportMessageForm(request.POST, request.FILES)
        message = TicketMessage(
            message=form.data['message'],
            author=0,
            ticket_id=ticket_id,
            attachment=request.FILES['file'] if 'file' in request.FILES else '',
            read=0
        )
        message.save()
    for message in TicketMessage.objects.filter(ticket_id=ticket_id, author=1).all():
        message.read = True
        message.save()
    ticket_messages = TicketMessage.objects.filter(ticket_id=ticket_id).all()
    return render(request, 'accounts/ticket.html', {'msgs': ticket_messages, 'ticket_id': ticket_id})


@login_required
def read_all(request, note_id):
    notifications = Notifications.objects.filter(customer=request.user.customer).all()
    for notification in notifications:
        notification.read = True
        notification.save()
    return JsonResponse({'status': True})


@login_required
def read(request, note_id):
    notification = Notifications.objects.get(id=note_id)
    notification.read = True
    notification.save()
    return JsonResponse({'status': True})


@login_required
def block(request):
    customer = Customer.objects.get(id=request.user.id)
    customer.account_status = 'blocked'
    customer.save()
    [s.delete() for s in Session.objects.all() if s.get_decoded().get('_auth_user_id') == request.user.id]
    logout(request)
    return redirect('login')


def logout_view(request):
    logout(request)
    return redirect('login')


def send_otp_email(request):
    email = request.GET.get('email', None)
    code = random.randint(100000, 999999)
    cache.set(f"email:otp:{email}", code, timeout=600)
    msg_body = f'''
        Здравствуйте!
        Ваш код для подтверждения e-mail:
        Код: {code}'''
    send_email(email, 'Подтверждение e-mail', msg_body)
    print(code)
    return JsonResponse({'status': True})


def send_reset_email(email):
    code = random.randint(100000, 999999)
    cache.set(f"email:otp:{email}", code, timeout=600)
    msg_body = f'''
        Здравствуйте!
        Мы получили запрос на регистрацию.
        Согласно данным системы, вы уже регистрировались с этим адресом email ранее. 
        Если вы забыли свой пароль, вы можете сбросить его здесь …..
        Если это были не вы, проверьте безопасность своей учетной записи или смените пароль

        Код авторизации: {code}'''
    send_email(email, 'Предупреждение о попытке регистрации', msg_body)
    print(code)
    return JsonResponse({'status': True})


def send_otp_telegram(request):
    telegram_id = request.GET.get('phone', None)
    code = random.randint(100000, 999999)
    cache.set(f"telegram:otp:{telegram_id}", code, timeout=600)
    msg_body = f'''Ваш код подтверждения учетной записи:
{code}'''
    print(code)
    send_tg(telegram_id, msg_body)
    return JsonResponse({'status': True})


def test(request):
    return render(request, 'test.html')
