# Submission readiness

This checklist reflects the local checkout. It does not imply that the GitHub
repository is public or that provider integrations have passed live tests.

## Ready in the local checkout

- [x] FastAPI backend and Streamlit interface.
- [x] Monthly plan, content generation, demo publishing, simulated analytics,
  and A/B workflow are covered by the local API test suite.
- [x] Russian technical specification in `Technical_Specification.docx`.
- [x] README with setup instructions and current prototype limitations.
- [x] Screenshots and screencast regenerated with a populated synthetic demo
  workflow, including the Instagram image URL field and visible demo-metrics
  notice.
- [x] Provider prerequisites and limitations are documented in
  [`INTEGRATIONS.md`](INTEGRATIONS.md).
- [x] Local test run: 7 passed using an isolated temporary SQLite database.
- [x] Owner confirmed the tracked database contains synthetic demo data; a
  secret-pattern scan of 17 reachable commits found no common OpenAI, GitHub,
  Telegram, or Mailchimp token formats.

## Still required before submission

- [x] Review the tracked `data/content_platform.db`: owner confirmed its
  project and five channel-account records are synthetic demo data. New local
  databases are ignored by Git.
- [ ] Make the GitHub repository public after reviewing its tracked files and
  commit history for private data and credentials.
- [ ] Regenerate screenshots and the screencast after final UI changes.
- [ ] For any channel described as live, configure and test it on an account
  that you own or are authorized to use; record sanitized evidence.
- [ ] Add the project link and specification to the Project №2 section of the
  Career Actions notebook, submit that notebook for review, then handle the
  portfolio and VIP-manager steps after feedback.

## Channel checklist

- [ ] Telegram: bot token and destination chat/channel ID.
- [ ] VK: community access token and numeric community ID.
- [ ] Instagram: Meta Graph API token and professional-account ID; public image
  URL required for feed publishing.
- [ ] WordPress: site URL, username, and Application Password.
- [ ] Mailchimp: API key, data-center prefix, audience ID, and authorized
  reply-to address. Live publication sends to that audience; test with a
  dedicated test audience only.

Never commit tokens or passwords. The current prototype reads provider secrets
from local environment settings and keeps them out of account-list API output.
