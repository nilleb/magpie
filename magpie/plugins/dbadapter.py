import peewee
from magpie.app import ReferenceAdapter, HOME, DEFAULT_CONFIGURATION
from typing import Callable, Optional, List, Iterable, Tuple


SQLITE_FILE_NAME = ".magpie.db"
DEFAULT_CONFIGURATION["sqlite.dbpath"] = HOME.joinpath(SQLITE_FILE_NAME)
DEFAULT_CONFIGURATION["database"] = "sqlite"  # also supported: postgresql, mysql

# if you wish to use postgresql or mysql, also provide

# dbadapter.db (str) (required)
# dbadapter.user (str)
# dbadapter.password (str)
# dbadapter.host (str)
# dbadapter.port (int)


class ReferenceData(peewee.Model):
    repository_id = peewee.CharField(80)
    commit_id = peewee.CharField(40)
    kind = peewee.CharField(40)
    subkind = peewee.CharField(40, null=True)
    branch = peewee.CharField(70, null=True)
    data = peewee.BlobField()
    collected_at = peewee.DateTimeField()
    filepath = peewee.CharField()

    class Meta:
        table_name = "timestamped_reference_data"
        primary_key = peewee.CompositeKey(
            "repository_id", "commit_id", "kind", "subkind"
        )


class DBProvider(object):
    def __init__(self, config):
        engine = config.get("database").lower()
        if engine == "sqlite":
            dbpath = config.get("sqlite.dbpath")
            self._db = peewee.SqliteDatabase(dbpath)
            self._db_info = {"engine": engine, "dbpath": dbpath}
        elif engine in ("postgres", "mysql"):
            db = config["dbadapter.db"]
            user = config.get("dbadapter.user")
            pwd = config.get("dbadapter.password")
            host = config.get("dbadapter.host")
            port = config.get("dbadapter.port")
            if port:
                port = int(port)
            clazz = (
                peewee.PostgresqlDatabase
                if engine == "postgres"
                else peewee.MySQLDatabase
            )
            self._db = clazz(db, user=user, password=pwd, host=host, port=port)
            self._db_info = {
                "engine": engine,
                "db": db,
                "user": user,
                "password": len(pws) * "*",
                "host": host,
                "port": port,
            }
        else:
            raise NameError(f"Database engine not supported: {engine}")

    @property
    def database(self):
        return self._db

    @property
    def database_info(self):
        return self._db_info


class DBReferenceAdapter(ReferenceAdapter):
    def __init__(self, repository_id, config) -> None:
        super().__init__(repository_id, config)

        self.db = DBProvider(config).database

        self.db.connect()
        ReferenceData.bind(self.db)
        self.db.create_tables([ReferenceData])

    def __exit__(self, exc_type, exc_value, traceback):
        self.db.close()

    def persist(
        self,
        commit_id: str,
        data: bytes,
        filepath: str,
        branch: str = None,
        kind: str = None,
        subkind: str = None,
    ):
        try:
            ReferenceData.create(
                repository_id=self.repository_id,
                commit_id=commit_id,
                kind=kind,
                subkind=subkind,
                filepath=filepath,
                branch=branch,
                data=data,
                collected_at=datetime.utcnow(),
            )
        except peewee.IntegrityError:
            logging.exception(
                "Another record seems to exist for this repository/commit/kind/subkind"
            )

    def get_commits(
        self, branch: str = None, kind: str = None, subkind: str = None, limit: int = -1
    ) -> frozenset:
        query = ReferenceData.select(ReferenceData.commit_id).where(
            ReferenceData.repository_id == self.repository_id,
            ReferenceData.kind == kind,
            ReferenceData.subkind == subkind,
        )
        if branch:
            query = query.where(ReferenceData.branch == branch)

        response = set()
        for item in query.order_by(-ReferenceData.collected_at).limit(limit):
            response.add(item.commit_id)
        return response

    def log(self, limit: int = -1) -> list:
        kinds_fn = peewee.fn.GROUP_CONCAT(ReferenceData.kind)
        subkinds_fn = peewee.fn.GROUP_CONCAT(ReferenceData.subkind)
        query = (
            ReferenceData.select(
                ReferenceData.commit_id,
                kinds_fn.alias("kinds"),
                subkinds_fn.alias("subkinds"),
            )
            .where(ReferenceData.repository_id == self.repository_id,)
            .group_by(ReferenceData.repository_id, ReferenceData.commit_id)
        )
        response = {}
        for item in query.limit(limit):
            kinds = item.kinds.split(",")
            subkinds = item.subkinds.split(",")
            response[item.commit_id] = [
                f"{val[:2]}:{subkinds[idx][:2]}" for idx, val in enumerate(kinds)
            ]
            logging.debug(response[item.commit_id])
        return response

    def retrieve_data(
        self, commit_id: str, kind: str = None, subkind: str = None
    ) -> Tuple[Optional[bytes], Optional[str]]:
        result = (
            ReferenceData.select(ReferenceData.data, ReferenceData.filepath)
            .where(
                ReferenceData.repository_id == self.repository_id,
                ReferenceData.commit_id == commit_id,
                ReferenceData.kind == kind,
                ReferenceData.subkind == subkind,
            )
            .order_by(-ReferenceData.collected_at)
            .get()
        )
        return result.data, result.filepath
