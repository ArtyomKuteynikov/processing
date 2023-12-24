import datetime
import time
import uuid
from functools import wraps

from django.contrib.auth.decorators import login_required
from django.shortcuts import render, redirect, get_object_or_404
from django.urls import reverse
import pyotp
from .forms import Step1Form, LoginForm, OTPForm, Reset1Form, Reset2Form, RequestForm, MerchantForm, SupportForm, \
    SupportMessageForm, CustomerChangeForm, WithdrawalForm, CardsForm, LimitsForm, ChoseMethodForm, KYCForm
from customer.models import Customer, Request, InviteCodes, Settings, User, TraderExchangeDirections, Cards, CardsLimits, Notifications, CustomerDocument
from order.models import Transaction, Order
from wallet.models import Balance, Withdrawal
from support.models import Ticket, FAQ, TicketMessage
from currency.models import Links, ExchangeDirection, PaymentMethods
import random
import redis
import qrcode
from interface.captcha import grecaptcha_verify
from django.contrib.auth import authenticate, login, logout
from django.http import JsonResponse, HttpResponseRedirect
from django.core.cache import cache
from .utils import send_email, send_tg, handle_uploaded_file
from passlib.context import CryptContext
from PIL import Image
from io import BytesIO
import base64
from django.db.models import Q

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
                time_zone=0
            )
            customer.save()
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
            if not user.email_is_verified or not user.phone_is_verified:
                return redirect(reverse('step2') + f'?customer={user.key}')
            if not user.password:
                return redirect(reverse('step3') + f'?customer={user.key}')
            if pwd_context.verify(password, user.password):
                key = str(uuid.uuid4())
                cache.set(f"otp:{key}", email, timeout=600)
                return redirect(reverse('2fa') + f'?session={key}')
            cache.set(f"retries:login:{email}", retries + 1, timeout=600)
            if retries >= 2:
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
        exists = is_user_exists(form.data['email'], form.data['phone_number'], '')
        if exists:
            form.add_error(None, 'Пользователь с такими учетными данными уже существует')
        if form.is_valid() and not exists:
            customer = Request.objects.create(
                email=form.data['email'],
                phone=form.data['phone_number'],
                site=form.data['website'],
                category=form.data['comment'],
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
        invite_code = InviteCodes.objects.filter(email=form.data['email'], code=form.data['invite_code'],
                                                 status=0).first()
        print(invite_code.expiry.date())
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
                time_zone=0
            )
            customer.save()
            return redirect(reverse('step2') + f'?customer={customer.key}')
    else:
        form = MerchantForm()
    return render(request, 'auth/merchant/step1.html', {'form': form})


@login_required
def kyc(request):
    form = KYCForm()
    verification = CustomerDocument.objects.filter(customer=request.user.customer).first()
    print(verification)
    if verification:
        form = KYCForm(instance=verification)
    if request.method == 'POST':
        """if verification:
            form = KYCForm(request.POST, request.FILES, instance=verification)
        else:"""
        form = KYCForm(request.POST, request.FILES)
        if form.is_valid():
            for file in request.FILES:
                print(file)
            # handle_uploaded_file(request.FILES['file'])
            return redirect('index')
        verification = form.save(commit=False)
        verification.customer = request.user.customer
        verification.save()
    return render(request, 'auth/trader/kyc.html', {'form': form, 'kyc': True})


@login_required
def index(request):
    return redirect('transactions')


@login_required
def transactions_view(request):
    balances = Balance.objects.filter(account=request.user).all()
    transactions = Transaction.objects.filter(Q(sender=request.user) | Q(receiver=request.user)).all()
    address = DEPOSIT_ADDRESS
    if Customer.objects.filter(user_ptr=request.user).first():
        max_amount = Settings.objects.first().trader_deposit_limit if request.user.customer.account_type == 'TRADER' else Settings.objects.first().merchant_deposit
    else:
        max_amount = 0
    form = WithdrawalForm()
    return render(request, 'accounts/transactions.html',
                  {'transactions': transactions[::-1], 'balances': balances, 'address': address, 'max_amount': max_amount,
                   'form': form})


@login_required
def orders_view(request):
    TIME_LIMIT = Settings.objects.first().order_life
    balances = Balance.objects.filter(account=request.user).all()
    orders = Order.objects.filter(Q(sender=request.user) | Q(trader=request.user)).all().order_by('-created')
    address = DEPOSIT_ADDRESS
    if Customer.objects.filter(user_ptr=request.user).first():
        max_amount = Settings.objects.first().trader_deposit_limit if request.user.customer.account_type == 'TRADER' else Settings.objects.first().merchant_deposit
    else:
        max_amount = 0
    form = WithdrawalForm()
    return render(request, 'accounts/orders.html',
                  {'orders': orders, 'balances': balances, 'address': address, 'max_amount': max_amount, 'form': form})


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
        traders = [i for i in traders if i.trader.verification_status().lower() == 'verified' and i.trader.status.lower() == 'active']
        print(traders)
        if not traders:
            order.status = 4
            order.save()
            merchant_balance = Balance.objects.get(account=order.sender, balance_link=order.output_link)
            merchant_balance.amount = merchant_balance.amount + order.output_amount
            merchant_balance.frozen = merchant_balance.frozen - order.output_amount
            merchant_balance.save()
            if order.side == 'OUT':
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
    if pwd_context.verify(str(order.client_id), str(key)):
        order.status = 3
        order.save()
        transaction = Transaction.objects.get(other_id_1=order.id)
        transaction.status = 1
        transaction.finished = True
        transaction.save()
        merchant_balance = Balance.objects.get(account=order.sender, balance_link=order.output_link)
        trader_balance = Balance.objects.get(account=order.trader, balance_link=order.output_link)
        merchant_balance.frozen = merchant_balance.frozen - order.output_amount
        trader_balance.amount = trader_balance.amount + order.output_amount
        merchant_balance.save()
        trader_balance.save()
        notification = Notifications(
            customer=order.trader,
            title=f"Ордер №{order.id} выполнен",
            body=f"Ордер №{order.id} выполнен, средства переведены",
            link='/orders',
            category='order'
        )
        notification.save()
        notification = Notifications(
            customer=order.sender,
            title=f"Ордер №{order.id} выполнен",
            body=f"Ордер №{order.id} выполнен, средства переведены трейдеру",
            link='/orders',
            category='order'
        )
        notification.save()
        return JsonResponse({'status': order.status})
    return JsonResponse({'status': -1})


@login_required
def realise_crypro_trader(request, order_id):
    order = Order.objects.get(id=order_id)
    if not order:
        return JsonResponse({'status': -1})
    if order.trader == request.user.customer:
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
            receiver_id=order.trader_id,
            site_id=order.order_site_id,
            link_id=order.output_link_id,
            amount=order.output_amount*order.trader.interest_rate/100,
            finished=True,
            type=6,
            status=1,
            counted='1',
            other_id_1=order.id,
            category='Комиссия трейдера',
            created=datetime.datetime.now(),
            updated=datetime.datetime.now(),
        )
        transaction_commission.save()
        merchant_balance = Balance.objects.get(account=order.sender, balance_link=order.output_link)
        trader_balance = Balance.objects.get(account=order.trader, balance_link=order.output_link)
        merchant_balance.amount = merchant_balance.amount + order.output_amount - order.output_amount*order.trader.interest_rate/100
        trader_balance.amount = trader_balance.amount - order.output_amount + order.output_amount*order.trader.interest_rate/100
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
        notification = Notifications(
            customer=order.sender,
            title=f"Ордер №{order.id} выполнен",
            body=f"Ордер №{order.id} выполнен, средства переведены",
            link='/orders',
            category='order'
        )
        notification.save()
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
    balances = Balance.objects.filter(account=request.user).all()
    withdrawals = Withdrawal.objects.filter(customer=request.user.customer).all()
    print(len(withdrawals))
    address = DEPOSIT_ADDRESS
    if Customer.objects.filter(user_ptr=request.user).first():
        max_amount = Settings.objects.first().trader_deposit_limit if request.user.customer.account_type == 'TRADER' else Settings.objects.first().merchant_deposit
    else:
        max_amount = 0
    form = WithdrawalForm()
    return render(request, 'accounts/withdrawals.html',
                  {'withdrawals': withdrawals[::-1], 'balances': balances, 'address': address, 'max_amount': max_amount,
                   'form': form})


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
            input_operation_limit=0,
            input_day_limit=0,
            input_month_limit=0,
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
        user = User.objects.get(id=request.user.id)
        customer = Customer.objects.get(user_ptr=user)
        if form.is_valid():
            user.email = form.data['email']
            customer.phone = form.data['phone']
            user.save()
            customer.save()
        cache.set(f'restriction:{request.user.email}', 1, timeout=86400)
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
        code = request.data.get['code']
        if code == cache.get(f"email:otp:{request.user.customer.email}"):
            request.user.customer.method_2fa = 0
    else:
        code = random.randint(100000, 999999)
        cache.set(f"email:otp:{request.user.customer.email}", code, timeout=600)
        msg_body = f'''
                Здравствуйте!
                Мы получили запрос на отключение 2FA.
                Если это были не вы, проверьте безопасность своей учетной записи или смените пароль
    
                Код отключения 2FA: {code}'''
        send_email(request.user.customer.email, 'Предупреждение о попытке отключения 2FA', msg_body)
        print(code)
    return JsonResponse({'status': True})


@login_required
def support(request):
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
            attachment=form.data['file'],
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
            attachment=form.data['file'],
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
            attachment=form.data['file'],
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
