# Pin jscpd when running it locally

On the rare run the user asks for locally, use `npx jscpd@5.0.16`, the
version CI installs. A bare `npx jscpd` can resolve to a cached 4.x, which
skips files over 1000 lines and so reports no clones in the very file CI
is failing on. Otherwise [[let-ci-run-the-checks]].
