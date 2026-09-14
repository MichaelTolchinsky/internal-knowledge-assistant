# Deployment Process

Production deployments happen through the `deploy` GitHub Actions workflow, triggered
automatically whenever a pull request is merged to `main`. There is no manual deploy button -
merging to `main` is the only way to ship to production, which keeps the deployment history
identical to the commit history.

The workflow runs the full test suite, builds a container image, pushes it to the internal
registry, and then performs a rolling deployment across all application instances one at a time,
waiting for each instance's health check to pass before moving to the next. A full rollout
typically takes 8-12 minutes for the application tier.

Database migrations are applied as a separate step before the application rollout begins, using
a dedicated migration job rather than running migrations from application startup code - this
avoids multiple instances racing to apply the same migration during a rolling deploy.

If a deployment's health checks fail partway through, the workflow automatically halts the
rollout and leaves the previously healthy instances running the old version - it does not
automatically roll back the instances that already updated. A manual rollback is triggered by
re-running the workflow against the last known-good commit.

Deployments are blocked outside of business hours (9am-6pm on weekdays) unless the pull request
is labeled `hotfix`, in which case the time restriction is skipped.
