# Observer behavior

Source of truth: user-supplied Important Email vertical slice and gorilla/core.py's guarded operations.
Canonical owners: native buttons for folder navigation; web/app.js for persisted URL folder, polling and inline connection status; server.py for read-only observer routes. No forms, selection controls, editable tables, or mutation buttons are present.
Inbox, Archive and Trash are read views. Empty folders explain the next useful read. Connection errors preserve the last received state. Pending decisions show no committed mutation. Historical decision content does not become editable.
The same decision ID connects all six stages. Probabilities are labeled uncalibrated; no model reasoning is invented. Operator audit content is never a customer-facing view.
Known boundary: read access is intended for the local hackathon operator; bind only to required host bridge and use an SSH tunnel for remote viewing.
