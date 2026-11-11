# Channel integration setup

The project supports five channel types in its prototype: Telegram, VK,
Instagram, WordPress, and Mailchimp. `POSTING_MODE=demo` records a simulated
publication and does not contact these providers. Live publishing is not
verified until each provider is configured and tested against an account that
you own or are authorized to use.

## Credentials and targets

Keep credentials in a local `.env` file copied from [`.env.example`](../.env.example).
Do not put tokens in screenshots, commits, issue comments, or this document.
The current account-connection API stores a masked token only; live adapters
read credentials from environment variables. Configure the target identifiers
listed below in the relevant project's account record where applicable.

| Channel | Credentials | Target / prerequisites |
|---|---|---|
| Telegram | `TELEGRAM_BOT_TOKEN` | `username` on the account should be the destination chat ID or `@channel`; add the bot to the chat and grant posting rights. |
| VK | `VK_ACCESS_TOKEN` | `username` should contain the community ID; issue a token with the needed wall-post permission. |
| Instagram | `IG_ACCESS_TOKEN` | `username` should be the professional Instagram account ID. The account must meet Meta Graph API publishing requirements. Supply a publicly reachable HTTPS image URL when generating Instagram content; video and carousel formats are not implemented. |
| WordPress | `WP_URL`, `WP_USER`, `WP_APP_PASSWORD` | Use a site you administer and a dedicated WordPress Application Password. |
| Mailchimp | `MAILCHIMP_API_KEY`, `MAILCHIMP_SERVER`, `MAILCHIMP_AUDIENCE_ID`, `MAILCHIMP_REPLY_TO` | Use your account's data-center prefix, audience ID, and an authorized reply-to address. Live publication sends a campaign to that audience; use a test audience and explicitly review the campaign before enabling this path. |

## What can be demonstrated now

- Run the app in `POSTING_MODE=demo` to demonstrate planning, copy generation,
  simulated publication, demo analytics, and A/B evaluation without external
  side effects.
- OpenAPI and the Streamlit UI can be demonstrated locally.
- Provider-specific live behavior and provider-backed analytics are not covered
  by the demo. Credentials alone do not establish that an integration works;
  verify each live adapter on a test destination before presenting it as live.

## Live acceptance checklist

For every channel being claimed as live, record the provider, test destination,
date, result, external post/campaign ID, and any restrictions. Never include a
credential in the evidence. Mailchimp tests should use a test audience and be
reviewed before sending. Instagram requires an image workflow before a real
feed post can be created. Live analytics collection is not implemented in the
current prototype and must not be presented as real channel data.
