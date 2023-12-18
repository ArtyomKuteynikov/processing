from django.db import models
from customer.models import Customer
from django.db.models import Count, Q
from ckeditor.fields import RichTextField


TICKET_STATUSES = [
    (0, 'New'),
    (1, 'Solving'),
    (2, 'Solved')
]


class Ticket(models.Model):
    client = models.ForeignKey(Customer, on_delete=models.CASCADE)
    title = models.CharField(max_length=128)
    status = models.IntegerField(choices=TICKET_STATUSES)
    priority = models.IntegerField()
    created = models.DateTimeField(auto_now_add=True)
    updated = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "support_ticket"
        ordering = ('priority', 'created',)
        verbose_name = "Ticket"
        verbose_name_plural = "Tickets"

    def unread(self):
        unresd_messages = TicketMessage.objects.filter(ticket=self, read=0, author=1).count()
        return unresd_messages or 0

    def __str__(self):
        return f'Ticket #{self.id}'


class TicketMessage(models.Model):
    ticket = models.ForeignKey(Ticket, on_delete=models.CASCADE)
    author = models.IntegerField(choices=[(0, 'Client'), (1, 'Support')])
    message = models.CharField(max_length=1024)
    read = models.BooleanField()
    attachment = models.FileField(verbose_name='message_attachment', upload_to='media', blank=True, null=True)
    created = models.DateTimeField(auto_now_add=True)
    updated = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "support_ticket_message"
        ordering = ('created',)
        verbose_name = "Ticket Message"
        verbose_name_plural = "Ticket Messages"


class FAQ(models.Model):
    title = models.CharField(max_length=128)
    text = RichTextField()
    created = models.DateTimeField(auto_now_add=True)
    updated = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "support_faq"
        ordering = ('created',)
        verbose_name = "FAQ"
        verbose_name_plural = "FAQs"
