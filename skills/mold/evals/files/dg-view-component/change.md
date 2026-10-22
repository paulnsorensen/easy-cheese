# Change: split the checkout service into pricing, tax, and promotions

The checkout service is one container today. The change stays inside it.
It adds a pricing module, a tax module, and a promotions module behind one controller.
The controller calls pricing. Pricing calls tax and promotions. The modules share no database table.
No other container, queue, or team changes.

Actors: buyer, checkout maintainer.

Tier: light.

Source: our own prompt.
