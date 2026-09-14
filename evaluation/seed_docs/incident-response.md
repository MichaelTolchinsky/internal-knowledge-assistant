# Incident Response Basics

Any engineer who notices a production issue can declare an incident by posting in the
`#incidents` channel with the `/incident` slash command - declaring an incident does not require
manager approval and it is explicitly encouraged to over-declare rather than wait to be sure.

Declaring an incident automatically creates a dedicated incident channel, pages the current
on-call engineer for the affected service, and starts a timeline document that is used later for
the post-incident review. The engineer who declares the incident is the "incident commander"
until someone else explicitly takes over that role in the channel.

Incidents are assigned a severity from SEV1 (full outage or data loss, all hands, immediate
customer communication) to SEV4 (minor, cosmetic, no customer impact) - severity can be
downgraded or upgraded at any point as more information comes in, and is not fixed at
declaration time.

A post-incident review is mandatory for SEV1 and SEV2 incidents, optional but encouraged for
SEV3, and not required for SEV4. Reviews are blameless by policy - the write-up focuses on
contributing factors and follow-up actions, not on which individual made a mistake.

Customer-facing status page updates are the incident commander's responsibility for SEV1 and
SEV2 incidents; SEV3 and SEV4 incidents do not get a public status page update by default.
