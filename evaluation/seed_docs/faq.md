# Frequently Asked Questions

**Q: How do I reset my own account password?**
Use the "Forgot password" link on the login page - it sends a reset email valid for 1 hour. There
is no way for support staff to reset a password on a customer's behalf; they can only re-trigger
the same reset email.

**Q: Can I have more than one API key per account?**
Yes - accounts can have up to 5 active API keys at once, which is the recommended way to give
each integration its own key (see the API rate limits doc for why this matters for rate
limiting). Creating a 6th key requires deleting one of the existing 5 first.

**Q: Does the platform support single sign-on (SSO)?**
SSO via SAML is available on Enterprise plans only, and must be configured by support - there is
no self-service SSO setup for any plan tier today.

**Q: What happens to my data if I downgrade my plan instead of cancelling?**
Downgrading does not trigger the data-deletion countdown described in the data retention policy -
that only starts on full cancellation. Downgrading may reduce which features remain accessible,
but existing data is left in place.

**Q: Who do I contact for a security vulnerability report?**
Security reports go to the security team via the responsible-disclosure form linked in the footer
of the marketing site, not through regular support - regular support tickets about security
reports are re-routed there, which adds delay, so using the form directly is faster.
