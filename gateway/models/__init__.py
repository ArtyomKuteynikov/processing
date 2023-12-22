import uuid

from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy import (Boolean, Column, ForeignKey, Integer, String, DateTime, Date, BigInteger, Time, REAL, func,
                        Float)
from datetime import datetime
from sqlalchemy.orm import relationship
from passlib.context import CryptContext
from sqlalchemy import select

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

Base = declarative_base()


class User(Base):
    __tablename__ = 'auth_user'
    id = Column(Integer, primary_key=True, index=True)
    email = Column(String, unique=True, index=True)
    password = Column(String(1024), nullable=True)

    customer = relationship("Customer", back_populates="user", uselist=False)


class Customer(Base):
    __tablename__ = "customer"
    user_ptr_id = Column(Integer, ForeignKey('auth_user.id'), unique=True, primary_key=True, index=True)
    account_type = Column(String(256), nullable=False)
    account_status = Column(String(256), nullable=False)
    status = Column(String(256), nullable=False)
    phone = Column(String(20), nullable=True)
    telegram_id = Column(String(128), nullable=True)
    email_is_verified = Column(Boolean, default=False)
    phone_is_verified = Column(Boolean, default=False)
    key = Column(String(1024), nullable=False)
    lang_code = Column(String(10), nullable=False)
    method_2fa = Column(Integer, nullable=True)
    value_2fa = Column(String(1024), nullable=True)
    time_zone = Column(Integer, nullable=False)
    created = Column(DateTime(timezone=True), server_default=func.now())
    updated = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    interest_rate = Column(Float, nullable=True)

    websites = relationship("Websites", back_populates="customer")
    # balances = relationship("Balance", back_populates="account")
    user = relationship("User", back_populates="customer", primaryjoin="Customer.user_ptr_id == User.id", uselist=False)

    def get_password_hash(self, password):
        self.user.password = pwd_context.hash(password)
        return pwd_context.hash(password)

    def verify_password(self, plain_password):
        if not self.user.password or len(self.user.password) < 250:
            self.user.password = pwd_context.hash('default')
        return pwd_context.verify(plain_password, self.user.password)

    def set_token(self):
        self.key = str(uuid.uuid4())
        return self.key

    def reset_token(self):
        self.key = str(uuid.uuid4())


class Websites(Base):
    __tablename__ = "customer_websites"

    id = Column(Integer, primary_key=True, index=True)
    merchant_id = Column(Integer, ForeignKey("customer.user_ptr_id"))
    domain = Column(String(128))
    status = Column(Integer, nullable=True)  # Assuming WEBSITES_STATUSES is an integer field
    payment_method = Column(Integer, nullable=True)  # Assuming PAYMENT_METHODS is an integer field
    verified = Column(Integer, nullable=True)  # Assuming WEBSITES_VERIFICATION is an integer field
    verification_code = Column(String(64))
    currency_id = Column(Integer, ForeignKey("currency_curr_token.id"))
    created = Column(DateTime(timezone=True), default=datetime.utcnow)
    updated = Column(DateTime(timezone=True), default=datetime.utcnow)

    customer = relationship("Customer", back_populates="websites")

    class Config:
        orm_mode = True


class Currency(Base):
    __tablename__ = "currency_curr_token"
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(100))
    ticker = Column(String(10))
    denomination = Column(Integer)
    active = Column(Boolean, default=True)

    links = relationship("Link", back_populates="currency")

    class Config:
        orm_mode = True


class Network(Base):
    __tablename__ = "currency_curr_net"
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(100))
    short_name = Column(String(10))
    standard = Column(String(20))
    active = Column(Boolean, default=True)

    links = relationship("Link", back_populates="network")

    class Config:
        orm_mode = True


class PaymentMethod(Base):
    __tablename__ = "currency_curr_method"
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(100))
    short_name = Column(String(10))
    active = Column(Boolean, default=True)

    links = relationship("Link", back_populates="method")

    class Config:
        orm_mode = True


class Link(Base):
    __tablename__ = "currency_curr_link"
    id = Column(Integer, primary_key=True, index=True)
    currency_id = Column(Integer, ForeignKey("currency_curr_token.id"))
    network_id = Column(Integer, ForeignKey("currency_curr_net.id"))
    method_id = Column(Integer, ForeignKey("currency_curr_method.id"))
    active = Column(Boolean, default=True)
    created = Column(DateTime(timezone=True), default=datetime.utcnow)

    currency = relationship("Currency", back_populates="links")
    network = relationship("Network", back_populates="links")
    method = relationship("PaymentMethod", back_populates="links")

    class Config:
        orm_mode = True


class ExchangeDirection(Base):
    __tablename__ = "currency_exchange_direction"

    id = Column(Integer, primary_key=True, index=True)
    input_id = Column(Integer, ForeignKey("currency_curr_link.id"))
    output_id = Column(Integer, ForeignKey("currency_curr_link.id"))
    spread = Column(Float)
    active = Column(Boolean, default=True)
    created = Column(DateTime(timezone=True), default=datetime.utcnow)

    input_currency = relationship("Link", foreign_keys=[input_id])
    output_currency = relationship("Link", foreign_keys=[output_id])

    class Config:
        orm_mode = True


class Order(Base):
    __tablename__ = "order_order"
    id = Column(Integer, primary_key=True, index=True)
    sender_id = Column(Integer, ForeignKey("customer.user_ptr_id"))
    trader_id = Column(Integer, ForeignKey("customer.user_ptr_id"), nullable=True)
    input_link_id = Column(Integer, ForeignKey("currency_curr_link.id"))
    output_link_id = Column(Integer, ForeignKey("currency_curr_link.id"))
    order_site_id = Column(Integer, ForeignKey("customer_websites.id"), nullable=True)
    input_amount = Column(Float, nullable=True)
    output_amount = Column(Float, nullable=True)
    status = Column(Integer, nullable=True)
    comment = Column(String(1024))
    created = Column(DateTime(timezone=True), default=datetime.utcnow)
    updated = Column(DateTime(timezone=True), default=datetime.utcnow)
    uuid = Column(String(128))
    method_id = Column(Integer, ForeignKey('currency_curr_method.id'), nullable=True)
    side = Column(String(4))
    payment_method_id = Column(Integer, ForeignKey('currency_curr_method.id'), nullable=True)
    payment_details = Column(String(256), nullable=True)
    initials = Column(String(256), nullable=True)

    class Config:
        orm_mode = True


class TraderPaymentMethod(Base):
    __tablename__ = "customer_traderpaymentmethod"
    id = Column(Integer, primary_key=True, index=True)
    method_id = Column(Integer, ForeignKey("currency_curr_method.id"))
    customer_id = Column(Integer, ForeignKey("customer.user_ptr_id"))
    payment_details = Column(String(256))
    initials = Column(String(256))


class Balance(Base):
    __tablename__ = "wallet_balance"
    id = Column(Integer, primary_key=True, index=True)
    account_id = Column(Integer, ForeignKey("customer.user_ptr_id"))
    balance_link_id = Column(Integer, ForeignKey("currency_curr_link.id"))
    amount = Column(Float)
    frozen = Column(Float, default=0)
    created = Column(DateTime(timezone=True), default=datetime.utcnow)
    updated = Column(DateTime(timezone=True), default=datetime.utcnow)

    # account = relationship("Customer", back_populates="balances")  # Assuming a one-to-many relationship with Customer
    # balance_link = relationship("Link", back_populates="balances")
