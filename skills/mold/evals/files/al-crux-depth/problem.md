# Problem: a daily email digest

Users of a work tool get many notifications. They want one digest email a day, at a local morning hour, in place of many emails.

The feature has many routine parts: a preferences page, an admin switch, sign-in checks, and an email template.

Two parts are risky. The first is delivery: the email provider can time out and retry, and a user must not get two digests. The second is timing: users live in many time zones, and a late job must still send a correct digest once.

Actors: user who reads the digest, support engineer, platform team.

Tier: light.

Source: our own prompt. The depth rule paraphrases the staff-level advice at <https://www.hellointerview.com/blog/staff-level-system-design> (link only; no text copied).
