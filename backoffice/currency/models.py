from django.db import models


class Currency(models.Model):
    name = models.CharField(max_length=100)
    ticker = models.CharField(max_length=10)
    denomination = models.IntegerField()
    active = models.BooleanField(default=True)

    class Meta:
        db_table = "currency_curr_token"
        ordering = ('name',)
        verbose_name = "Currency"
        verbose_name_plural = "Currencies"

    def __str__(self):
        return self.name


class Networks(models.Model):
    name = models.CharField(max_length=100)
    short_name = models.CharField(max_length=10)
    standard = models.CharField(max_length=20)
    active = models.BooleanField(default=True)

    class Meta:
        db_table = "currency_curr_net"
        ordering = ('name',)
        verbose_name = "Network"
        verbose_name_plural = "Networks"

    def __str__(self):
        return self.name


class PaymentMethods(models.Model):
    name = models.CharField(max_length=100)
    short_name = models.CharField(max_length=10)
    active = models.BooleanField(default=True)

    class Meta:
        db_table = "currency_curr_method"
        ordering = ('name',)
        verbose_name = "Payment Method"
        verbose_name_plural = "Payment Methods"

    def __str__(self):
        return self.name


class Links(models.Model):
    currency = models.ForeignKey(Currency, on_delete=models.CASCADE)
    network = models.ForeignKey(Networks, on_delete=models.CASCADE, null=True, blank=True)
    method = models.ForeignKey(PaymentMethods, on_delete=models.CASCADE, null=True, blank=True)
    active = models.BooleanField(default=True)
    created = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "currency_curr_link"
        ordering = ('created',)
        verbose_name = "Link"
        verbose_name_plural = "Links"

    def __str__(self):
        return f'{self.currency.ticker}_{self.network.short_name}' if self.network else f'{self.currency.ticker}_{self.method.short_name}'


class ExchangeDirection(models.Model):
    input = models.ForeignKey(Links, on_delete=models.CASCADE, related_name='input')
    output = models.ForeignKey(Links, on_delete=models.CASCADE, related_name='output')
    spread = models.FloatField()
    active = models.BooleanField(default=True)
    created = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "currency_exchange_direction"
        ordering = ('created',)
        verbose_name = "Exchange direction"
        verbose_name_plural = "Exchange directions"

    def __str__(self):
        return f'{self.input.currency.ticker}/{self.output.currency.ticker}'
