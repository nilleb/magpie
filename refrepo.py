import argparse
import yaml
import peewee
from datetime import datetime
import logging
import shlex
import subprocess
import sys
from pathlib import Path
from typing import Callable, Optional, List, Iterable

__version__ = "dev~"

HOME = Path.home()
CONFIG_FILE_NAME = ".refrepo.yml"
DB_FILE_NAME = ".refrepo.db"
KNOWN_ADAPTERS = {
    "default": "SqliteAdapter",
}
DEFAULT_CONFIGURATION = {
    "sqlite.dbpath": HOME.joinpath(DB_FILE_NAME),
    "known.adapters": KNOWN_ADAPTERS,
}


def get_output(command, working_folder=None):
    logging.debug("Executing %s in %s", command, working_folder)

    try:
        output = subprocess.check_output(shlex.split(command), cwd=working_folder)
        return output.decode("utf-8")
    except OSError:
        logging.error("Command being executed: {}".format(command))
        raise


class GitAdapter(object):
    def __init__(self, repository_folder=".", repository_desambiguate=None):
        self.repository_folder = repository_folder
        self.repository_desambiguate = repository_desambiguate

    def get_repository_id(self):
        repository_id = get_output(
            "git rev-list --max-parents=0 HEAD", working_folder=self.repository_folder
        ).rstrip()

        if self.repository_desambiguate:
            repository_id = "{}_{}".format(repository_id, self.repository_desambiguate)

        return repository_id

    def get_current_commit_id(self):
        return get_output(
            "git rev-parse HEAD", working_folder=self.repository_folder
        ).rstrip()

    def iter_git_commits(self, refs: List[str] = None) -> Iterable[str]:
        if not refs:
            refs = ["HEAD^"]

        count = 0
        while True:
            skip = "--skip={}".format(100 * count) if count else ""
            command = "git rev-list {} --max-count=100 {}".format(skip, " ".join(refs))
            commits = get_output(command, working_folder=self.repository_folder).split(
                "\n"
            )
            commits = [commit for commit in commits if commit]
            if not commits:
                return
            count += 1
            logging.debug("Returning as previous revisions: %r", commits)
            yield commits

    def get_files(self):
        root_folder = self.get_root_path()
        command = "git ls-files"
        output = get_output(command, working_folder=root_folder)
        files = output.split("\n")
        if not files[-1]:
            files = files[:-1]
        return set(files)

    def get_common_ancestor(self, base_branch="origin/master", ref="HEAD"):
        command = "git merge-base {} {}".format(base_branch, ref)
        try:
            return get_output(command, working_folder=self.repository_folder).rstrip()
        except subprocess.CalledProcessError:
            return None
        # at the moment, CircleCI does not provide the name of the base|target branch
        # https://ideas.circleci.com/ideas/CCI-I-894

    def get_root_path(self):
        command = "git rev-parse --show-toplevel"
        return get_output(command, working_folder=self.repository_folder).rstrip()

    def get_current_branch(self):
        command = "git rev-parse --abbrev-ref HEAD"
        return get_output(command, working_folder=self.repository_folder).rstrip()


class ReferenceAdapter(object):
    def __init__(self, repository_id, config) -> None:
        self.config = config
        self.repository_id = repository_id

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        pass

    def get_commits(
        self, branch=None, kind: str = None, subkind: str = None, limit=1,
    ) -> frozenset:
        raise NotImplementedError

    def retrieve_data(self, commit_id: str, kind: str = None, subkind: str = None) -> Optional[bytes]:
        raise NotImplementedError

    def persist(
        self, commit_id: str, data: bytes, branch: str = None, kind: str=None, subkind: str = None
    ):
        raise NotImplementedError
    
db = peewee.SqliteDatabase(DB_FILE_NAME)

class ReferenceData(peewee.Model):
    repository_id = peewee.CharField(80)
    commit_id = peewee.CharField(40)
    kind = peewee.CharField(40)
    subkind = peewee.CharField(40, null=True)
    branch = peewee.CharField(70, null=True)
    data = peewee.BlobField()
    collected_at = peewee.DateTimeField()

    class Meta:
        database = db
        table_name = "timestamped_reference_data"

class SqliteAdapter(ReferenceAdapter):
    def __init__(self, repository_id, config) -> None:
        super().__init__(repository_id, config)
        db.connect()
        db.create_tables([ReferenceData])

    def __exit__(self, exc_type, exc_value, traceback):
        db.close()

    def persist(self, commit_id: str, data: bytes, branch: str, kind: str, subkind: str):
        record = ReferenceData(
            repository_id=self.repository_id, commit_id=commit_id, kind=kind, subkind=subkind,
            branch=branch, data=data, collected_at=datetime.utcnow())
        record.save()

    def get_commits(self, branch: str=None, kind: str=None, subkind: str=None, limit: int=-1) -> frozenset:
        return ReferenceData.select(
            ReferenceData.commit_id
        ).where(
            ReferenceData.branch == branch, ReferenceData.kind == kind, ReferenceData.subkind == subkind
        ).order_by(-ReferenceData.collected_at).limit(limit)

    def retrieve_data(self, commit_id: str, kind: str = None, subkind: str = None) -> Optional[bytes]:
        return ReferenceData.select(
            ReferenceData.commit_id
        ).where(
            ReferenceData.commit_id == commit_id, ReferenceData.kind == kind, ReferenceData.subkind == subkind
        ).order_by(-ReferenceData.collected_at).get()


def iter_callable(git, ref):
    def call():
        return git.iter_git_commits([ref])

    return call


def determine_parent_commit(
    db_commits: frozenset, iter_callable: Callable
) -> Optional[str]:
    for commits_chunk in iter_callable():
        for commit in commits_chunk:
            if commit in db_commits:
                return commit
    return None


def str_to_class(classname):
    return getattr(sys.modules[__name__], classname)


def adapter_factory(adapter: str, config: dict) -> ReferenceAdapter:
    selected = adapter or config.get("adapter.class", None) or "default"
    return str_to_class(KNOWN_ADAPTERS[selected])


def configuration(repository_path="."):
    user_config = HOME.joinpath(CONFIG_FILE_NAME)
    repository_config = Path(repository_path).joinpath(CONFIG_FILE_NAME)

    paths = [user_config, repository_config]
    config = dict(DEFAULT_CONFIGURATION)
    for path in paths:
        logging.debug("Considering %s as configuration file", path)
        try:
            with open(path) as config_fd:
                config.update(yaml.load(config_fd, Loader=yaml.CLoader))
        except FileNotFoundError:
            logging.debug("File %s has not been found", path)
    return config


def parse_common_args(parser=None):
    if not parser:
        parser = argparse.ArgumentParser(
            description=(
                "You can only improve! Compare Code Coverage and prevent regressions."
            )
        )

    parser.add_argument(
        "--adapter",
        help="Choose the adapter to use (choices: sqlite, default)",
        dest="adapter",
        default="default"
    )
    parser.add_argument(
        "--debug",
        dest="debug",
        help="whether to print debug messages",
        action="store_true",
    )
    parser.add_argument(
        "--repository", dest="repository", help="the repository to analyze", default="."
    )
    parser.add_argument(
        "-d",
        "--repository-desambiguate",
        dest="repository_id_modifier",
        help="A token to distinguish repositories with the same first commit ID.",
    )
    parser.add_argument(
        "-k",
        "--kind",
        dest="kind",
        default="unspecified",
        help="Define the kind of metric being collected. `cc` for Code Coverage, for example.",
    )
    parser.add_argument(
        "-s",
        "--subkind",
        dest="subkind",
        help="A supplementary characteristic of the metric being collected."
        "Whether the code coverage has been colllected during the execution of "
        "unit tests or integration tests, for example.",
    )

def parse_args(args=None, parser=None):
    if not parser:
        parser = argparse.ArgumentParser(
            description=(
                "Store and retrieve reference data associated to your repository commits."
            )
        )

    parse_common_args(parser)

    parser.add_argument(
        "data",
        nargs='?',
        help="the reference data for the current commit ID"
    )

    parser.add_argument(
        "--target-branch",
        dest="target_branch",
        help="the branch to which this code will be merged (default: origin/master)",
        default="origin/master",
    )
    parser.add_argument(
        "--branch",
        dest="branch",
        help="the name of the branch to which this code belongs to",
    )
    parser.add_argument(
        "--consider-uncommitted-changes",
        dest="uncommitted",
        help="whether to consider uncommitted changes. reference will not be persisted.",
        action="store_true",
    )

    return parser.parse_args(args)


def persist(
    repo_adapter: GitAdapter,
    reference_adapter: ReferenceAdapter,
    report_file: str,
    branch: str = None,
    kind: str=None,
    subkind: str = None,
    logging_module=logging
):
    with open(report_file, "rb") as fd:
        data = fd.read()
        current_commit = repo_adapter.get_current_commit_id()
        branch = branch if branch else repo_adapter.get_current_branch()
        reference_adapter.persist(current_commit, data, branch, kind, subkind)
        logging_module.info("Data for commit %s persisted successfully.", current_commit)


def retrieve(
    repo_adapter: GitAdapter,
    reference_adapter: ReferenceAdapter,
    target_branch: str= None,
    kind: str=None,
    subkind: str=None,
    consider_uncommitted: bool=False,
    logging_module=logging
):
    reference_commits = reference_adapter.get_commits(kind=kind, subkind=subkind)
    logging_module.debug(
        "Found the following reference commits: %r", reference_commits
    )

    common_ancestor = repo_adapter.get_common_ancestor(target_branch)

    commit_id = None

    if common_ancestor:
        current_commit_id = repo_adapter.get_current_commit_id()
        if common_ancestor == current_commit_id and not consider_uncommitted:
            ref = "{}^".format(common_ancestor)
        else:
            ref = common_ancestor

        commit_id = determine_parent_commit(
            reference_commits, iter_callable(repo_adapter, ref)
        )

    if commit_id:
        logging_module.info(f"Retrieving data for reference commit %{commit_id}")
        reference_data = reference_adapter.retrieve_data(
            commit_id, kind=kind, subkind=subkind
        )
        logging_module.debug(f"Reference data: {reference_data is None}")
        if not reference_data:
            logging_module.error("No data for the selected reference.")
    else:
        logging_module.warning("No reference data found.")


def main(args=None, logging_module=logging):
    args = parse_args(args)

    if args.debug:
        logging_module.getLogger().setLevel(logging.DEBUG)
    else:
        logging_module.getLogger().setLevel(logging.INFO)

    git = GitAdapter(args.repository, args.repository_id_modifier)
    repository_id = git.get_repository_id()
    logging_module.info("Your repository ID is %s", repository_id)

    config = configuration(args.repository)

    with adapter_factory(args.adapter, config)(repository_id, config) as adapter:
        if args.data:
            persist(git, adapter, args.data, args.branch, args.kind, args.subkind)
            return
        retrieve(git, adapter, args.target_branch, args.kind, args.subkind, args.uncommitted)


if __name__ == "__main__":
    main()
