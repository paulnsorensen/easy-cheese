# Change: add invoices and invoice lines

The change adds two tables: invoices and invoice_lines.
An invoice belongs to one customer. An invoice has many lines. A line refers to one product.
The tables hold the amount in minor units and a currency code.
The risk is the keys and the relations between the tables.

Actors: billing staff, customer.

Tier: light.

Source: our own prompt.
