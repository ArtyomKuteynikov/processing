from datetime import datetime
from typing import List, Union, Any
from pydantic import BaseModel


class CaptchaData(BaseModel):
    lot_number: str
    gen_time: str
    captcha_output: str
    pass_token: str


class UserLogin(BaseModel):
    username: str
    password: str
    uuid: str


class UserSignUp(BaseModel):
    username: str
    email: str
    phone: str
    password: str
    confirm_password: str
    uuid: str


class Customer(BaseModel):
    id: int
    name: str
    surname: str
    email: str
    phone: str
    legal_address: str
    password: str
    entity_type: bool
    legal_company_name: str
    legal_registration_number: str
    activated_email_2fa: bool
    activated_phone_2fa: bool
    activated_ga_2fa: bool
    email_is_verified: bool
    phone_is_verified: bool
    is_verified: bool
    is_active: bool


class Asset(BaseModel):
    id: int
    name: str
    code: str
    image: str
    market_rate: float


class OrderStatus(BaseModel):
    id: str
    name: str


class PaymentMethodItems(BaseModel):
    id: int
    name: str


class AddCustomerPaymentMethod(BaseModel):
    payment_method_item: int
    condition: str


class PaymentMethod(BaseModel):
    id: int
    label: str
    selected: bool
    paymentMethodItems: List[PaymentMethodItems] = []


class Currency(BaseModel):
    id: int
    label: str
    market_rate: float


class Country(BaseModel):
    id: int
    label: str


class AssetsResponse(BaseModel):
    assets: List[Asset]
    paymentMethods: List[PaymentMethod]
    currencies: List[Currency]
    countries: List[Country]


class ExchangeResponse(BaseModel):
    assets: List[Asset]
    paymentMethods: List[PaymentMethod]
    currencies: List[Currency]


class WalletAsset(BaseModel):
    name: str
    sign: str


class Balance(BaseModel):
    available: float
    all: float
    rolling: float
    hold: float


class WalletContent(BaseModel):
    asset: WalletAsset
    balance: Balance
    address: str


class MyWallet(BaseModel):
    content: List[WalletContent]


class Operation(BaseModel):
    date: str
    commission: float
    exchange_rate: float
    counterparty: int
    details: int
    type: str


class WalletHistoryModel(BaseModel):
    date: int
    type: str
    wallet: str
    asset: str
    sum: str
    destionation: str
    txid: str
    status: str


class Response(BaseModel):
    success: bool
    msg: str
    error_code: int
    results: Any | ExchangeResponse | None = None


class EmailData(BaseModel):
    email: str
    uuid: str


class PhoneData(BaseModel):
    phone: str
    uuid: str


class EmailOtp(BaseModel):
    email: str
    code: int
    uuid: str


class PhoneOtp(BaseModel):
    phone: str
    code: int
    uuid: str


class VerifyOtp(BaseModel):
    result: bool


class OfferSchema(BaseModel):
    id: int
    creator_id: int
    terms: str
    payment_id: int
    country_id: int
    asset_id: int
    currency_id: int
    price_setting: str
    price: str
    margin_percent: int
    payment_details: str
    min_transaction_limit: int
    max_transaction_limit: int
    track_liquidity: bool
    escrow_time: int
    anonym_user_allowed: bool
    customer_phone_verified: bool
    customer_identy_verified: bool
    preview_minimum_trade_volume: int
    new_customer_max_limit_trade: int
    trade_conditions: str
    offer_type: str


class OfferData(BaseModel):
    offer_type: str
    #   scheduler_day: None
    country_id: int
    asset_id: int
    currency_id: int
    price_setting: str
    price: str
    margin_percent: int
    payment_id: int
    min_transaction_limit: float
    max_transaction_limit: float
    escrow_time: int
    customer_phone_verified: bool
    customer_identy_verified: bool
    trade_conditions: str


class CreateOrder(BaseModel):
    key: str
    output_link: str
    website: int
    amount: float | None = None
    quantity: float | None = None
    comment: str | None = None
    payment_detail: str | None = None
    initials: str | None = None
    side: str | None = 'IN'


class OrderFilterSchema(BaseModel):
    assets: List[Asset]
    statuses: List[OrderStatus]


class OfferList(BaseModel):
    offer_id: int
    price: float
    margin: float
    min_limit: float
    max_limit: float
    payment_method: int
    anonymous_user_allowed: bool
    customer_phone_verified: bool
    customer_identy_verified: bool
