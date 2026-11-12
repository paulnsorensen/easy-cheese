# Change: add a search service

A request from the browser reaches the web app. The web app calls a new search service. The search service reads a search index.
The web app still reads the main database for everything else.
The search service and its index are new.
The spec must show what the parts are and how they connect. The order of the calls is not the risk.

Actors: buyer, search maintainer.

Tier: full.

Source: our own prompt.
