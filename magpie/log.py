import git
import logging

class AnnotatedCommit(git.Commit):
    def __init__(self, commit, kinds):
        self.commit = commit
        self.has_ref = bool(kinds)
        self.kinds = kinds

    @property
    def shortsha(self):
        return self.commit.hexsha[:7]

    @property
    def message(self):
        return next(iter(self.commit.message.split("\n")))[:70]

    @property
    def kinds_pretty(self):
        if self.has_ref:
            return " ".join([f"|{kind}|" for kind in self.kinds])
        else:
            return "{:9}".format("")

    @property
    def pretty(self):
        return f"{'✅' if self.has_ref else '❌'} {self.shortsha:<7} {self.kinds_pretty:<25} {self.message:<72}‧"

    def __str__(self):
        return self.pretty

    def __repr__(self):
        return self.pretty


def annotated_log(repo_folder, adapter, limit):
    repo = git.Repo(repo_folder, search_parent_directories=True)
    items = adapter.log(limit)
    references = {key: value for key, value in items.items()}

    def enrich_commit(commit):
        return AnnotatedCommit(commit, references.get(commit.hexsha, None))

    return [
        enrich_commit(repo.commit(logEntry))
        for logEntry in list(repo.iter_commits())[:limit]
    ]
