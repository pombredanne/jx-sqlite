# encoding: utf-8
#
#
# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this file,
# You can obtain one at http:# mozilla.org/MPL/2.0/.
#
# Author: Kyle Lahnakoski (kyle@lahnakoski.com)
#


from __future__ import absolute_import
from __future__ import division
from __future__ import unicode_literals

from collections import OrderedDict

from mo_dots import listwrap, join_field
from mo_kwargs import override

from jx_sqlite import GUID, typed_column, quote_table, quoted_UID, _quote_column, sql_types, untyped_column
from pyLibrary.queries import jx, Index
from pyLibrary.queries.containers import Container
from pyLibrary.queries.meta import Column
from pyLibrary.sql.sqlite import Sqlite


_config=None


class BaseTable(Container):
    @override
    def __init__(self, name, db=None, uid=GUID, exists=False, kwargs=None):
        """
        :param name: NAME FOR THIS TABLE
        :param db: THE DB TO USE
        :param uid: THE UNIQUE INDEX FOR THIS TABLE
        :return: HANDLE FOR TABLE IN db
        """
        global _config
        Container.__init__(self, frum=None)
        if db:
            self.db = db
        else:
            self.db = db = Sqlite()

        if not _config:
            from pyLibrary.queries.containers import config as _config
            if not _config.default:
                _config.default = {
                    "type": "sqlite",
                    "settings": {"db": db}
                }

        self.name = name
        self.uid = listwrap(uid)
        self._next_uid = 1
        self._make_digits_table()

        self.uid_accessor = jx.get(self.uid)
        self.nested_tables = OrderedDict()  # MAP FROM NESTED PATH TO Table OBJECT, PARENTS PROCEED CHILDREN
        self.nested_tables["."] = self
        self.columns = Index(keys=[join_field(["names", self.name])])  # MAP FROM DOCUMENT ABS PROPERTY NAME TO THE SET OF SQL COLUMNS IT REPRESENTS (ONE FOR EACH REALIZED DATATYPE)

        if not exists:
            for u in self.uid:
                if u == GUID:
                    pass
                else:
                    c = Column(
                        names={name: u},
                        type="string",
                        es_column=typed_column(u, "string"),
                        es_index=name
                    )
                    self.add_column_to_schema(self.nested_tables, c)

            command = (
                "CREATE TABLE " + quote_table(name) + "(" +
                (",".join(
                    [quoted_UID + " INTEGER"] +
                    [_quote_column(c) + " " + sql_types[c.type] for u, cs in self.columns.items() for c in cs]
                )) +
                ", PRIMARY KEY (" +
                (", ".join(
                    [quoted_UID] +
                    [_quote_column(c) for u in self.uid for c in self.columns[u]]
                )) +
                "))"
            )

            self.db.execute(command)
        else:
            # LOAD THE COLUMNS
            command = "PRAGMA table_info(" + quote_table(name) + ")"
            details = self.db.query(command)

            for r in details:
                cname = untyped_column(r[1])
                ctype = r[2].lower()
                column = Column(
                    names={name: cname},
                    type=ctype,
                    nested_path=['.'],
                    es_column=typed_column(cname, ctype),
                    es_index=name
                )

                self.add_column_to_schema(self.columns, column)
                # TODO: FOR ALL TABLES, FIND THE MAX ID

    def quote_column(self, column, table=None):
        return self.db.quote_column(column, table)

    def _make_digits_table(self):
        existence = self.db.query("PRAGMA table_info(__digits__)")
        if not existence.data:
            self.db.execute("CREATE TABLE __digits__(value INTEGER)")
            self.db.execute("INSERT INTO __digits__ " + "\nUNION ALL ".join("SELECT " + unicode(i) for i in range(10)))

    def next_uid(self):
        try:
            return self._next_uid
        finally:
            self._next_uid += 1


