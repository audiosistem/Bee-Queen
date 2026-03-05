from tmdbhelper.lib.query.database.daily_export import TableDailyExport


class FindQueriesDatabaseKeywords:

    keywords_columns = {
        'id': {
            'data': 'INTEGER PRIMARY KEY',
            'indexed': True
        },
        'name': {
            'data': 'TEXT'
        },
    }

    @property
    def keywords_daily_export(self):
        daily_export = TableDailyExport(self)
        daily_export.table = 'keywords'
        daily_export.keys = ('id', 'name', )
        daily_export.export_list = 'keyword'
        return daily_export

    def get_keywords(self, limit=250, page=1):
        daily_export = self.keywords_daily_export
        daily_export.conditions = f'name IS NOT NULL ORDER BY id LIMIT {limit}'
        daily_export.conditions = f'{daily_export.conditions} OFFSET {((limit * page) - limit)}'
        return daily_export.get_cached() or daily_export.set_cached()

    def get_keyword_by_id(self, tmdb_id):
        daily_export = self.keywords_daily_export
        daily_export.conditions = f'id={tmdb_id}'
        value = daily_export.get_cached() or daily_export.set_cached()
        if not value:
            return
        return value[0]['name']
