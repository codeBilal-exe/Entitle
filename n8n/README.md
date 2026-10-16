# n8n workflows

Export each workflow as JSON into this folder after you build it on Alternate Clouds.

Planned workflows:
- W1 Source Watcher (cron + webhook)
- W2 Impact Fan-out (webhook from Core after curator approve)
- W3 Approved Send (optional orchestration around Core send)

Core already performs Pulse fan-out in-process so the demo works if n8n is unavailable.
n8n should call Core with header `x-rightpath-secret` and only pass IDs.
