# README

## The problem magpie solves

To speed up your development process and commit safely, you want to execute your entire tests suite. But sometimes this takes a little while. You could be tempted to use a tool like `crystalball`, but even with that the first execution will take long.

Here comes `magpie`. You usually have a CI server, whose job is _just_ to execute unit tests. `magpie` will store the `tmp/crystallball.yml` data to a central repository and let every developer retrieve it when needed.
