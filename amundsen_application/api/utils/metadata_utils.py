from typing import Any, Dict

from amundsen_common.models.popular_table import PopularTable, PopularTableSchema
from amundsen_common.models.table import Table, TableSchema
from amundsen_application.models.user import load_user, dump_user
from flask import current_app as app


def marshall_table_partial(table_dict: Dict) -> Dict:
    """
    Forms a short version of a table Dict, with selected fields and an added 'key'
    :param table: Dict of partial table object
    :return: partial table Dict

    TODO - Unify data format returned by search and metadata.
    """
    schema = PopularTableSchema(strict=True)
    # TODO: consider migrating to validate() instead of roundtripping
    table: PopularTable = schema.load(table_dict).data
    results = schema.dump(table).data
    # TODO: fix popular tables to provide these? remove if we're not using them?
    # TODO: Add the 'key' or 'id' to the base PopularTableSchema
    results['key'] = f'{table.database}://{table.cluster}.{table.schema}/{ table.name}'
    results['last_updated_timestamp'] = None
    results['type'] = 'table'

    return results


def marshall_table_full(table_dict: Dict) -> Dict:
    """
    Forms the full version of a table Dict, with additional and sanitized fields
    :param table: Table Dict from metadata service
    :return: Table Dict with sanitized fields
    """

    schema = TableSchema(strict=True)
    # TODO: consider migrating to validate() instead of roundtripping
    table: Table = schema.load(table_dict).data
    results: Dict[str, Any] = schema.dump(table).data

    is_editable = results['schema'] not in app.config['UNEDITABLE_SCHEMAS']
    results['is_editable'] = is_editable

    # TODO - Cleanup https://github.com/lyft/amundsen/issues/296
    #  This code will try to supplement some missing data since the data here is incomplete.
    #  Once the metadata service response provides complete user objects we can remove this.
    results['owners'] = [_map_user_object_to_schema(owner) for owner in results['owners']]
    readers = results['table_readers']
    for reader_object in readers:
        reader_object['user'] = _map_user_object_to_schema(reader_object['user'])

    # If order is provided, we sort the column based on the pre-defined order
    if app.config['COLUMN_STAT_ORDER']:
        columns = results['columns']
        for col in columns:
            # the stat_type isn't defined in COLUMN_STAT_ORDER, we just use the max index for sorting
            col['stats'].sort(key=lambda x: app.config['COLUMN_STAT_ORDER'].
                              get(x['stat_type'], len(app.config['COLUMN_STAT_ORDER'])))
            col['is_editable'] = is_editable

    # TODO: Add the 'key' or 'id' to the base TableSchema
    results['key'] = f'{table.database}://{table.cluster}.{table.schema}/{ table.name}'
    # Temp code to make 'partition_key' and 'partition_value' part of the table
    results['partition'] = _get_partition_data(results['watermarks'])
    return results


def _map_user_object_to_schema(u: Dict) -> Dict:
    return dump_user(load_user(u))


def _get_partition_data(watermarks: Dict) -> Dict:
    if watermarks:
        high_watermark = next(filter(lambda x: x['watermark_type'] == 'high_watermark', watermarks))
        if high_watermark:
            return {
                'is_partitioned': True,
                'key': high_watermark['partition_key'],
                'value': high_watermark['partition_value']
            }
    return {
        'is_partitioned': False
    }
