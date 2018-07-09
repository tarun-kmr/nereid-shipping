# -*- coding: utf-8 -*-
"""
    checkout

    :copyright: (c) 2015 by Fulfil.IO Inc.
    :license: see LICENSE for details.
"""
import json
from decimal import Decimal

from trytond.pool import Pool, PoolMeta
from trytond.exceptions import UserError
from trytond.modules.nereid_checkout.checkout import not_empty_cart, \
    sale_has_non_guest_party
from nereid import route, redirect, url_for, render_template, \
    request, flash, current_website
from trytond.modules.nereid_checkout.signals import cart_address_updated
from trytond.modules.nereid_cart_b2c.signals import cart_updated


__metaclass__ = PoolMeta
__all__ = ['Checkout', 'Cart']


class Cart:
    __name__ = 'nereid.cart'

    @cart_address_updated.connect
    @cart_updated.connect
    def delete_shipping_line(self):
        """
        Deleting shipping lines whenever the cart or addresss is being updated
        """
        SaleLine = Pool().get('sale.line')

        if not self.sale:
            return

        for line in self.sale.lines:
            if not line.shipment_cost:
                continue
            SaleLine.delete([line])


class Checkout:
    __name__ = 'nereid.checkout'

    @classmethod
    @route('/checkout/delivery-method', methods=['GET', 'POST'])
    @not_empty_cart
    @sale_has_non_guest_party
    def delivery_method(cls):
        '''
        Selection of delivery method (options)

        Based on the shipping address selected, the delivery options
        could be shown to the user. This may include choosing shipping speed
        and if there are multiple items, the option to choose items as they are
        available or all at once.
        '''
        NereidCart = Pool().get('nereid.cart')
        Carrier = Pool().get('carrier')
        CarrierService = Pool().get('carrier.service')
        Currency = Pool().get('currency.currency')
        cart_sale = NereidCart.open_cart().sale
        if not cart_sale.shipment_address:
            return redirect(url_for('nereid.checkout.shipping_address'))

        if not cart_sale.weight:
            # No weight, no shipping. Have fun !
            return redirect(url_for('nereid.checkout.payment_method'))

        if request.method == 'POST' and request.form.get('carrier_json'):
            rate = json.loads(request.form.get('carrier_json'))
            rate.update({
                'carrier': Carrier(rate['carrier']),
                'carrier_service': CarrierService(rate['carrier_service']),
                'cost_currency': Currency(rate['cost_currency']),
                'cost': Decimal("%s" % (rate['cost'], ))
            })
            cart_sale.apply_shipping_rate(rate)
            return redirect(url_for('nereid.checkout.payment_method'))

        delivery_rates = []
        try:
            delivery_rates = cart_sale.get_shipping_rates(
                current_website.carriers,
                silent=True
            )
        except UserError, e:
            # Possible Errors: Overweighted shipment, Invalid address
            # TODO: Handle gracefully
            flash(e.message)
            return redirect(url_for('nereid.checkout.shipping_address'))

        return render_template(
            'checkout/delivery_method.jinja', delivery_rates=delivery_rates,
            sale=cart_sale
        )
