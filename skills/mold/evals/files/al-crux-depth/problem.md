# Problem: a daily email digest

Users of a work tool get many notifications. They want one digest email a day, at a local morning hour, in place of many emails.

The feature has many routine parts: a preferences page, an admin switch, sign-in checks, and an email template.

Two parts are risky. The first is delivery: the email provider can time out and retry, and a user must not get two digests. The second is timing: users live in many time zones, and a late job must still send a correct digest once.

The email provider drops a repeated send that carries the same idempotency key within 24 hours. The digest jobs run on the existing job runner and keep their send records in its existing job store. No container or data store is added.

## Recorded user decisions

The user made this choice in an earlier dialogue round. It is not an agent decision.

- D-1 (user): a late run still sends that day's digest once, until local midnight. After local midnight, the run skips that digest and logs the skip.
- Open (no user decision yet): whether each user picks their own morning hour, or every user gets the digest at 8:00 local time.

Actors: user who reads the digest, support engineer, platform team.

Tier: light.

Source: our own prompt. The depth rule paraphrases the staff-level advice at <https://www.hellointerview.com/blog/staff-level-system-design> (link only; no text copied).
