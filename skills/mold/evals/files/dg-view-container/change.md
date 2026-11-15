# Change: move report export out of the web app

The web app builds PDF reports inside the request. Big accounts time out.
The change adds a report service with its own worker and a reports bucket.
The web app calls the service over HTTPS. The worker reads from the main database and writes to the bucket.
No team outside this repo changes.

Actors: account owner, on-call engineer.

Tier: full.

Source: our own prompt.
