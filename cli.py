import click
import logging

from magpie import GitAdapter, configuration, adapter_factory, persist, choose_and_retrieve


class MagpieTask:
    def __init__(
        self,
        repository,
        repository_desambiguate,
        kind,
        subkind,
        reference_adapter_name,
        verbose,
    ):
        self.repository = repository
        self.repository_id_modifier = repository_desambiguate
        self.kind = kind
        self.subkind = subkind
        self.config = {}
        self.reference_adapter_name = reference_adapter_name
        self.verbose = verbose

    def __repr__(self):
        return f"<Magpie {self.repository}>"

    def _get_git_repository(self):
        git = GitAdapter(self.repository, self.repository_id_modifier)
        repository_id = git.get_repository_id()
        logging.info("Your repository ID is %s", repository_id)
        return git, repository_id

    def persist(self, data, branch):
        git, repository_id = self._get_git_repository()
        config = configuration(self.repository)

        with adapter_factory(self.reference_adapter_name, config)(
            repository_id, config
        ) as adapter:
            persist(git, adapter, data, branch, self.kind, self.subkind)

    def retrieve(self, target_branch, consider_uncommitted_changes):
        git, repository_id = self._get_git_repository()
        config = configuration(self.repository)

        with adapter_factory(self.reference_adapter_name, config)(
            repository_id, config
        ) as adapter:
            choose_and_retrieve(
                repo_adapter=git,
                reference_adapter=adapter,
                target_branch=target_branch,
                kind=self.kind,
                subkind=self.subkind,
                consider_uncommitted=consider_uncommitted_changes,
            )


pass_magpie = click.make_pass_decorator(MagpieTask)


@click.group()
@click.option(
    "--adapter",
    help="Choose the reference adapter to use (choices: sqlite, default)",
)
@click.option(
    "--debug",
    is_flag=True,
    help="whether to print debug messages",
)
@click.option(
    "--repository",
    help="the repository to analyze",
    default=".",
)
@click.option(
    "-d",
    "--repository-desambiguate",
    help="A token to distinguish repositories with the same first commit ID.",
)
@click.option(
    "-k",
    "--kind",
    default="unspecified",
    help="Define the kind of metric being collected. `cc` for Code Coverage, for example.",
)
@click.option(
    "-s",
    "--subkind",
    default="unspecified",
    help="A supplementary characteristic of the metric being collected."
    "Whether the code coverage has been colllected during the execution of "
    "unit tests or integration tests, for example.",
)
@click.pass_context
def cli(ctx, adapter, debug, repository, repository_desambiguate, kind, subkind):
    if debug:
        logging.getLogger().setLevel(logging.DEBUG)
    else:
        logging.getLogger().setLevel(logging.INFO)

    ctx.obj = MagpieTask(
        repository, repository_desambiguate, kind, subkind, adapter, debug
    )


@cli.command()
@click.option(
    "-b", "--branch", help="the name of the branch to which this code belongs to"
)
@click.argument("data")
@pass_magpie
def pick(magpie, data, branch):
    click.echo(f"pick {data} (in {magpie.repository})")
    magpie.persist(data, branch)


@cli.command()
@click.option(
    "--target-branch",
    default="origin/master",
    help="the branch to which this code will be merged (default: origin/master)",
)
@click.option(
    "--consider-uncommitted-changes",
    is_flag=True,
    default=False,
    help="whether to consider uncommitted changes.",
)
@pass_magpie
def retrieve(magpie, target_branch, consider_uncommitted_changes):
    click.echo(f"retrieve (in {magpie.repository})")

    magpie.retrieve(target_branch, consider_uncommitted_changes)


if __name__ == "__main__":
    cli()
