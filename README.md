# README

Magpie allows you to collect raw data related to a git repository.

It's extensible, it's configurable.

## The problems magpie solves

### Central repository

#### Ruby test coverage data - to determine which tests run following your next change

To speed up your development process and commit safely, you want to execute your entire tests suite. But sometimes this takes a little while. You could be tempted to use a tool like `crystalball`, but even with that the first execution will take long.

Here comes `magpie`. You usually have a CI server, whose job is _just_ to execute unit tests. `magpie` will store the `tmp/crystallball.yml` data to a central repository and let every developer retrieve it when needed.

#### Python - Collect code coverage and fail whether your current coverage is less than past

#### Golang - same as in python, but convert the code coverage to a generic format

### Raw -> refined

Let's imagine you have collected a certain amount of data, and now you want to expose a new set of properties about the data you have collected.
Magpie allows you to refine the past data, so to extract only what you need and determine trends.
