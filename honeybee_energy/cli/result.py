"""honeybee energy result parsing commands."""

try:
    import click
except ImportError:
    raise ImportError(
        'click is not installed. Try `pip install . [cli]` command.'
    )

from honeybee_energy.result.match import match_rooms_to_data, match_faces_to_data
from honeybee_energy.result.loadbalance import LoadBalance

from honeybee.model import Model
from honeybee.face import Face
from ladybug.datacollection import HourlyContinuousCollection, DailyCollection, \
    MonthlyCollection
from ladybug.sql import SQLiteResult
from ladybug.dt import Date

import sys
import logging
import os
import json

_logger = logging.getLogger(__name__)


@click.group(help='Commands for parsing EnergyPlus results.')
def result():
    pass


@result.command('available-results')
@click.argument('result-sql', type=click.Path(
    exists=True, file_okay=True, dir_okay=False, resolve_path=True))
@click.option('--output-file', '-f', help='Optional file to output the list of available'
              ' outputs. By default, it will be printed to stdout',
              type=click.File('w'), default='-', show_default=True)
def available_results(result_sql, output_file):
    """Get an array of all timeseries outputs within an sql file.

    \b
    Args:
        result_sql: Full path to an SQLite file that was generated by EnergyPlus.
    """
    try:
        sql_obj = SQLiteResult(result_sql)
        output_file.write(json.dumps(sql_obj.available_outputs))
    except Exception as e:
        _logger.exception('Failed to parse sql file.\n{}'.format(e))
        sys.exit(1)
    else:
        sys.exit(0)


@result.command('available-results-info')
@click.argument('result-sql', type=click.Path(
    exists=True, file_okay=True, dir_okay=False, resolve_path=True))
@click.option('--output-file', '-f', help='Optional file to output the list of available'
              ' outputs. By default, it will be printed to stdout',
              type=click.File('w'), default='-', show_default=True)
def available_results_info(result_sql, output_file):
    """Get all timeseries outputs within an sql file and metadata about them.

    \b
    Args:
        result_sql: Full path to an SQLite file that was generated by EnergyPlus.
    """
    try:
        sql_obj = SQLiteResult(result_sql)
        all_info = []
        for outp_dict in sql_obj.available_outputs_info:
            clean_dict = {
                'output_name': outp_dict['output_name'],
                'object_type': outp_dict['object_type'],
                'units': outp_dict['units']
            }
            d_type = outp_dict['data_type']
            clean_dict['units_ip'] = d_type.ip_units[0]
            clean_dict['cumulative'] = d_type.cumulative
            if d_type.normalized_type is not None:
                norm_type = d_type.normalized_type()
                clean_dict['normalized_units'] = norm_type.units[0]
                clean_dict['normalized_units_ip'] = norm_type.ip_units[0]
            else:
                clean_dict['normalized_units'] = None
                clean_dict['normalized_units_ip'] = None
            all_info.append(clean_dict)
        output_file.write(json.dumps(all_info))
    except Exception as e:
        _logger.exception('Failed to parse sql file.\n{}'.format(e))
        sys.exit(1)
    else:
        sys.exit(0)


@result.command('available-run-period-info')
@click.argument('result-sql', type=click.Path(
    exists=True, file_okay=True, dir_okay=False, resolve_path=True))
@click.option('--output-file', '-f', help='Optional file to output the list of available'
              ' outputs. By default, it will be printed to stdout',
              type=click.File('w'), default='-', show_default=True)
def available_run_period_info(result_sql, output_file):
    """Get an array of run period info within an sql file.

    \b
    Args:
        result_sql: Full path to an SQLite file that was generated by EnergyPlus.
    """
    try:
        sql_obj = SQLiteResult(result_sql)
        time_int = sql_obj.reporting_frequency
        all_info = []
        for runper, per_name in zip(sql_obj.run_periods, sql_obj.run_period_names):
            clean_dict = {
                'name': per_name,
                'time_interval ': time_int,
                'start_date ': [runper.st_month, runper.st_day],
                'end_date  ': [runper.end_month, runper.end_day]
            }
            all_info.append(clean_dict)
        output_file.write(json.dumps(all_info))
    except Exception as e:
        _logger.exception('Failed to parse sql file.\n{}'.format(e))
        sys.exit(1)
    else:
        sys.exit(0)


@result.command('all-available-info')
@click.argument('result-sql', type=click.Path(
    exists=True, file_okay=True, dir_okay=False, resolve_path=True))
@click.option('--output-file', '-f', help='Optional file to output the list of available'
              ' outputs. By default, it will be printed to stdout',
              type=click.File('w'), default='-', show_default=True)
def all_available_info(result_sql, output_file):
    """Get a dictionary with metadata of all outputs and run periods within an sql file.

    The dictionary will have two keys - 'run_periods', 'outputs'.

    \b
    Args:
        result_sql: Full path to an SQLite file that was generated by EnergyPlus.
    """
    try:
        # create the SQLiteResult object
        sql_obj = SQLiteResult(result_sql)
        all_info = {}

        # get all of the info on the outputs within the file
        all_outp = []
        for outp_dict in sql_obj.available_outputs_info:
            clean_dict = {
                'output_name': outp_dict['output_name'],
                'object_type': outp_dict['object_type'],
                'units': outp_dict['units']
            }
            d_type = outp_dict['data_type']
            clean_dict['units_ip'] = d_type.ip_units[0]
            clean_dict['cumulative'] = d_type.cumulative
            if d_type.normalized_type is not None:
                norm_type = d_type.normalized_type()
                clean_dict['normalized_units'] = norm_type.units[0]
                clean_dict['normalized_units_ip'] = norm_type.ip_units[0]
            else:
                clean_dict['normalized_units'] = None
                clean_dict['normalized_units_ip'] = None
            all_outp.append(clean_dict)
        all_info['outputs'] = all_outp

        # get all of the run periods within the fil
        time_int = sql_obj.reporting_frequency
        all_run_per = []
        for runper, per_name in zip(sql_obj.run_periods, sql_obj.run_period_names):
            clean_dict = {
                'name': per_name,
                'time_interval ': time_int,
                'start_date ': [runper.st_month, runper.st_day],
                'end_date  ': [runper.end_month, runper.end_day]
            }
            all_run_per.append(clean_dict)
        all_info['run_periods'] = all_run_per
        output_file.write(json.dumps(all_info))
    except Exception as e:
        _logger.exception('Failed to parse sql file.\n{}'.format(e))
        sys.exit(1)
    else:
        sys.exit(0)


@result.command('tabular-data')
@click.argument('result-sql', type=click.Path(
    exists=True, file_okay=True, dir_okay=False, resolve_path=True))
@click.argument('table-name', type=str)
@click.option('--output-file', '-f', help='Optional file to output the JSON matrix of '
              'tabular data. By default, it will be printed to stdout',
              type=click.File('w'), default='-', show_default=True)
def tabular_data(result_sql, table_name, output_file):
    """Get all the data within a table of a Summary Report using the table name.

    \b
    Args:
        result_sql: Full path to an SQLite file that was generated by EnergyPlus.
        table_name: Text string for the name of a table within a summary
            report. (eg. 'General').
    """
    try:
        sql_obj = SQLiteResult(result_sql)
        table_dict = sql_obj.tabular_data_by_name(str(table_name))
        output_file.write(json.dumps(list(table_dict.values())))
    except Exception as e:
        _logger.exception('Failed to retrieve table data from sql file.\n{}'.format(e))
        sys.exit(1)
    else:
        sys.exit(0)


@result.command('tabular-metadata')
@click.argument('result-sql', type=click.Path(
    exists=True, file_okay=True, dir_okay=False, resolve_path=True))
@click.argument('table-name', type=str)
@click.option('--output-file', '-f', help='Optional file to output the JSON matrix of '
              'tabular data. By default, it will be printed to stdout',
              type=click.File('w'), default='-', show_default=True)
def tabular_metadata(result_sql, table_name, output_file):
    """Get a dictionary with the names of a table's rows and columns.

    \b
    Args:
        result_sql: Full path to an SQLite file that was generated by EnergyPlus.
        table_name: Text string for the name of a table within a summary
            report. (eg. 'General').
    """
    try:
        sql_obj = SQLiteResult(result_sql)
        table_dict = sql_obj.tabular_data_by_name(str(table_name))
        row_names = list(table_dict.keys())
        col_names = sql_obj.tabular_column_names(str(table_name))
        output_file.write(json.dumps({'row_names': row_names, 'column_names': col_names}))
    except Exception as e:
        _logger.exception('Failed to retrieve table data from sql file.\n{}'.format(e))
        sys.exit(1)
    else:
        sys.exit(0)


@result.command('data-by-output')
@click.argument('result-sql', type=click.Path(
    exists=True, file_okay=True, dir_okay=False, resolve_path=True))
@click.argument('output-name', type=str)
@click.option('--output-file', '-f', help='Optional file to output the JSON strings of '
              'the data collections. By default, it will be printed to stdout',
              type=click.File('w'), default='-', show_default=True)
def data_by_output(result_sql, output_name, output_file):
    """Get an array of DataCollection JSONs for a specific EnergyPlus output.

    \b
    Args:
        result_sql: Full path to an SQLite file that was generated by EnergyPlus.
        output_name: The name of an EnergyPlus output to be retrieved from
            the SQLite result file. This can also be an array of names if the
            string is formatted as a JSON array with [] brackets. Note that only
            a single array of data collection JSONs will be returned from this
            method and, if data collections must be grouped, the data_by_outputs
            method should be used.
    """
    try:
        sql_obj = SQLiteResult(result_sql)
        output_name = str(output_name)
        if output_name.startswith('['):
            output_name = tuple(outp.replace('"', '').strip()
                                for outp in output_name.strip('[]').split(','))
        data_colls = sql_obj.data_collections_by_output_name(output_name)
        output_file.write(json.dumps([data.to_dict() for data in data_colls]))
    except Exception as e:
        _logger.exception('Failed to retrieve outputs from sql file.\n{}'.format(e))
        sys.exit(1)
    else:
        sys.exit(0)


@result.command('data-by-outputs')
@click.argument('result-sql', type=click.Path(
    exists=True, file_okay=True, dir_okay=False, resolve_path=True))
@click.argument('output-names', type=str, nargs=-1)
@click.option('--output-file', '-f', help='Optional file to output the JSON strings of '
              'the data collections. By default, it will be printed to stdout',
              type=click.File('w'), default='-', show_default=True)
def data_by_outputs(result_sql, output_names, output_file):
    """Get an array of DataCollection JSONs for a several EnergyPlus outputs.

    \b
    Args:
        result_sql: Full path to an SQLite file that was generated by EnergyPlus.
        output_names: An array of EnergyPlus output names to be retrieved from
            the SQLite result file. This can also be a nested array (an array of
            output name arrays) if each string is formatted as a JSON array
            with [] brackets.
    """
    try:
        sql_obj = SQLiteResult(result_sql)
        data_colls = []
        for output_name in output_names:
            output_name = str(output_name)
            if output_name.startswith('['):
                output_name = tuple(outp.replace('"', '').strip()
                                    for outp in output_name.strip('[]').split(','))
            data_cs = sql_obj.data_collections_by_output_name(output_name)
            data_colls.append([data.to_dict() for data in data_cs])
        output_file.write(json.dumps(data_colls))
    except Exception as e:
        _logger.exception('Failed to retrieve outputs from sql file.\n{}'.format(e))
        sys.exit(1)
    else:
        sys.exit(0)


@result.command('output-csv')
@click.argument('result-sql', type=click.Path(
    exists=True, file_okay=True, dir_okay=False, resolve_path=True))
@click.argument('output-names', type=str, nargs=-1)
@click.option('--output-file', '-f', help='Optional file path to output the CSV data of '
              'the results. By default, it will be printed to stdout',
              type=click.File('w'), default='-', show_default=True)
def output_csv(result_sql, output_names, output_file):
    """Get CSV for specific EnergyPlus outputs.

    \b
    Args:
        result_sql: Full path to an SQLite file that was generated by EnergyPlus.
        output_names: The name of an EnergyPlus output to be retrieved from
            the SQLite result file. This can also be several output names
            for which all data collections should be retrieved.
    """
    try:
        # get the data collections
        sql_obj = SQLiteResult(result_sql)
        data_colls = []
        for output_name in output_names:
            output_name = str(output_name)
            if output_name.startswith('['):
                output_name = tuple(outp.replace('"', '').strip()
                                    for outp in output_name.strip('[]').split(','))
            data_colls.extend(sql_obj.data_collections_by_output_name(output_name))

        # create the header rows
        type_row = ['DateTime'] + [data.header.metadata['type'] for data in data_colls]
        units_row = [''] + [data.header.unit for data in data_colls]
        obj_row = ['']
        for data in data_colls:
            try:
                obj_row.append(data.header.metadata['Zone'])
            except KeyError:
                try:
                    obj_row.append(data.header.metadata['Surface'])
                except KeyError:
                    try:
                        obj_row.append(data.header.metadata['System'])
                    except KeyError:
                        obj_row.append('')

        # create the data rows
        try:
            datetimes = [data_colls[0].datetimes]
        except IndexError:  # no data for the requested type
            datetimes = []
        val_columns = datetimes + [data.values for data in data_colls]

        # write everything into the output file
        def write_row(row):
            output_file.write(','.join([str(item) for item in row]) + '\n')
        write_row(type_row)
        write_row(units_row)
        write_row(obj_row)
        for row in zip(*val_columns):
            write_row(row)
    except Exception as e:
        _logger.exception('Failed to retrieve outputs from sql file.\n{}'.format(e))
        sys.exit(1)
    else:
        sys.exit(0)


@result.command('output-csv-queryable')
@click.argument('result-sql', type=click.Path(
    exists=True, file_okay=True, dir_okay=False, resolve_path=True))
@click.argument('model-json', type=click.Path(
    exists=True, file_okay=True, dir_okay=False, resolve_path=True))
@click.argument('run-period-name', type=str)
@click.argument('output-names', type=str, nargs=-1)
@click.option('--si/--ip', help='Flag to note whether the data in the resulting CSV '
              'should be in SI or IP units.', default=True, show_default=True)
@click.option('--normalize/--no-normalize', ' /-nn', help='Flag to note whether the '
              'data in the resulting CSV should be normalized by floor area (in the '
              'case of Zone/System data) or surface area (in the case of Surface data). '
              'This flag has no effect if the requested data is not normalizable',
              default=True, show_default=True)
@click.option('--folder', '-f', help='Folder on this computer, into which the CSV '
              'files will be written. If None, the files will be output in the'
              'same location as the result_sql.', default=None, show_default=True,
              type=click.Path(file_okay=False, dir_okay=True, resolve_path=True))
@click.option('--log-file', '-log', help='Optional file to output the names of the '
              'columns within the CSV. By default, it will be printed to stdout',
              type=click.File('w'), default='-', show_default=True)
def output_csv_queryable(result_sql, model_json, run_period_name, output_names,
                         si, normalize, folder, log_file):
    """Get CSV of outputs resembling a SQLite table that is easily queryable.

    \b
    Args:
        result_sql: Full path to an SQLite file that was generated by EnergyPlus.
        model_json: Full path to a Model JSON that will be matched with the results.
        run_period_name: The name of the run period from which the CSV data will
            be selected (eg. "BOSTON LOGAN INTL ARPT ANN CLG .4% CONDNS DB=>MWB").
        output_names: The name of an EnergyPlus output to be retrieved from
            the SQLite result file. This can also be several output names
            for which all data collections should be retrieved.
    """
    try:
        # figure out the index of the run period
        sql_obj = SQLiteResult(result_sql)
        per_names, per_indices = sql_obj.run_period_names, sql_obj.run_period_indices
        per_i = per_indices[per_names.index(run_period_name)]

        # get the data collections for each output
        data_colls = []
        for output_name in output_names:
            output_name = str(output_name)
            if output_name.startswith('['):
                output_names = tuple(outp.replace('"', '').strip()
                                     for outp in output_name.strip('[]').split(','))
                for outp in output_names:
                    col = sql_obj.data_collections_by_output_name_run_period(outp, per_i)
                    data_colls.append(col)
            else:
                col = sql_obj.data_collections_by_output_name_run_period(output_name, per_i)
                data_colls.append(col)

        # convert the data to IP if it was requested
        if not si:
            for colls in data_colls:
                for data in colls:
                    data.convert_to_ip()

        # re-serialize the Model to Python and ensure it's in correct SI/IP units
        with open(model_json) as json_file:
            data = json.load(json_file)
        model = Model.from_dict(data)
        if si:
            model.convert_to_units('Meters')
        else:
            model.convert_to_units('Feet')

        # match the objects in the Model to the data collections
        room_csv_data = []
        face_csv_data = []
        faces = None
        for colls in data_colls:
            if len(colls) == 0:
                continue
            if 'Surface' in colls[0].header.metadata:
                if faces is None:
                    faces = []
                    for room in model.rooms:
                        faces.extend(room.faces)
                match_data = match_faces_to_data(colls, faces)
                if len(match_data) != 0:
                    face_csv_data.append(match_data)
            elif 'Zone' in colls[0].header.metadata or 'System' in colls[0].header.metadata:
                match_data = match_rooms_to_data(colls, model.rooms)
                if len(match_data) != 0:
                    room_csv_data.append(match_data)
        assert len(room_csv_data) != 0 or len(face_csv_data) != 0, \
            'None of the requested outputs could be matched to the model_json.'

        # normalize the data if this was requested
        if normalize:
            for matched_data in face_csv_data:  # normalize face data
                if matched_data[0][1].header.data_type.normalized_type is not None:
                    for matched_tup in matched_data:
                        area = matched_tup[0].area if not isinstance(matched_tup, Face) \
                            else matched_tup[0].punched_geometry.area
                        matched_tup[1].values = \
                            [val / area for val in matched_tup[1].values]
        for matched_data in room_csv_data:  # normalize room data
            if normalize and matched_data[0][1].header.data_type.normalized_type is not None:
                for matched_tup in matched_data:
                    area = matched_tup[0].floor_area
                    try:
                        matched_tup[1].values = [val / (area * matched_tup[2])
                                                 for val in matched_tup[1].values]
                    except ZeroDivisionError:  # no floor area for room
                        matched_tup[1].values = [0] * len(matched_tup[1])
            else:  # we should still account for room multipliers
                matched_tup[1].values = \
                    [val / matched_tup[2] for val in matched_tup[1].values]

        # create the datetime columns
        base_coll = room_csv_data[0][0][1] if len(room_csv_data) != 0 else \
            face_csv_data[0][0][1]
        year = '2016' if base_coll.header.analysis_period.is_leap_year else '2017'
        date_times = []
        if isinstance(base_coll, HourlyContinuousCollection):
            for dat_t in base_coll.datetimes:
                date_times.append(
                    [year, str(dat_t.month), str(dat_t.day), str(dat_t.hour),
                     str(dat_t.minute)])
        elif isinstance(base_coll, DailyCollection):
            for dat_t in base_coll.datetimes:
                date_obj = Date.from_doy(dat_t)
                date_times.append(
                    [year, str(date_obj.month), str(date_obj.day), '0', '0'])
        elif isinstance(base_coll, MonthlyCollection):
            for dat_t in base_coll.datetimes:
                date_times.append([year, str(dat_t), '1', '0', '0'])

        # determine the output folder location
        if folder is None:
            folder = os.path.dirname(result_sql)

        # write everything into the output CSVs
        def write_rows(csv_file, datas, identifier):
            data_rows = [row[:] for row in date_times]  # copy datetimes
            for row in data_rows:
                row.append(identifier)
            for data in datas:
                for i, val in enumerate(data.values):
                    data_rows[i].append(str(val))
            for row in data_rows:
                csv_file.write(','.join(row) + '\n')

        col_names_dict = {}
        if len(room_csv_data) != 0:
            room_file = os.path.join(folder, 'eplusout_room.csv')
            col_names_dict['eplusout_room'] = \
                ['year', 'month', 'day', 'hour', 'minute', 'identifier'] + \
                [data[0][1].header.metadata['type'].replace(' ', '_').lower()
                 for data in room_csv_data]
            with open(room_file, 'w') as rm_file:
                rm_file.write(','.join(col_names_dict['eplusout_room']) + '\n')
                for outp_tups in zip(*room_csv_data):
                    datas = [tup[1] for tup in outp_tups]
                    identifier = outp_tups[0][0].identifier
                    write_rows(rm_file, datas, identifier)
        if len(face_csv_data) != 0:
            room_file = os.path.join(folder, 'eplusout_face.csv')
            col_names_dict['eplusout_face'] = \
                ['year', 'month', 'day', 'hour', 'minute', 'identifier'] + \
                [data[0][1].header.metadata['type'].replace(' ', '_').lower()
                 for data in face_csv_data]
            with open(room_file, 'w') as f_file:
                f_file.write(','.join(col_names_dict['eplusout_face']) + '\n')
                for outp_tups in zip(*face_csv_data):
                    datas = [tup[1] for tup in outp_tups]
                    identifier = outp_tups[0][0].identifier
                    write_rows(f_file, datas, identifier)

        # write the column names into the output file
        log_file.write(json.dumps(col_names_dict))
    except Exception as e:
        _logger.exception('Failed to write queryable csv from sql file.\n{}'.format(e))
        sys.exit(1)
    else:
        sys.exit(0)


@result.command('zone-sizes')
@click.argument('result-sql', type=click.Path(
    exists=True, file_okay=True, dir_okay=False, resolve_path=True))
@click.option('--output-file', '-f', help='Optional file to output the JSON strings of '
              'the ZoneSize objects. By default, it will be printed to stdout',
              type=click.File('w'), default='-', show_default=True)
def zone_sizes(result_sql, output_file):
    """Get a dictionary with two arrays of ZoneSize JSONs under 'cooling' and 'heating'.

    \b
    Args:
        result_sql: Full path to an SQLite file that was generated by EnergyPlus.
    """
    try:
        sql_obj = SQLiteResult(result_sql)
        base = {}
        base['cooling'] = [zs.to_dict() for zs in sql_obj.zone_cooling_sizes]
        base['heating'] = [zs.to_dict() for zs in sql_obj.zone_heating_sizes]
        output_file.write(json.dumps(base))
    except Exception as e:
        _logger.exception('Failed to retrieve zone sizes from sql file.\n{}'.format(e))
        sys.exit(1)
    else:
        sys.exit(0)


@result.command('component-sizes')
@click.argument('result-sql', type=click.Path(
    exists=True, file_okay=True, dir_okay=False, resolve_path=True))
@click.option('--component-type', '-ct', help='A name of a HVAC component type, which '
              'will be used to filter the output HVAC components. If None, all HVAC '
              'component sizes will be output.',
              type=str, default=None, show_default=True)
@click.option('--output-file', '-f', help='Optional file to output the JSON strings of '
              'the ComponentSize objects. By default, it will be printed to stdout',
              type=click.File('w'), default='-', show_default=True)
def component_sizes(result_sql, component_type, output_file):
    """Get a list of ComponentSize JSONs.

    \b
    Args:
        result_sql: Full path to an SQLite file that was generated by EnergyPlus.
    """
    try:
        sql_obj = SQLiteResult(result_sql)
        comp_sizes = []
        if component_type is None:
            for comp_size in sql_obj.component_sizes:
                comp_sizes.append(comp_size.to_dict())
        else:
            for comp_size in sql_obj.component_sizes_by_type(component_type):
                comp_sizes.append(comp_size.to_dict())
        output_file.write(json.dumps(comp_sizes))
    except Exception as e:
        _logger.exception('Failed to retrieve component sizes from sql.\n{}'.format(e))
        sys.exit(1)
    else:
        sys.exit(0)


@result.command('load-balance')
@click.argument('model-json', type=click.Path(
    exists=True, file_okay=True, dir_okay=False, resolve_path=True))
@click.argument('result-sql', type=click.Path(
    exists=True, file_okay=True, dir_okay=False, resolve_path=True))
@click.option('--normalize/--no-normalize', ' /-nn', help='Flag to note whether the '
              'data should be normalized by floor area. This flag has no effect if the '
              'requested data is not normalizable', default=True, show_default=True)
@click.option('--storage/--no-storage', ' /-ns', help='to note whether the storage term '
              'should be included in the list.', default=True, show_default=True)
@click.option('--output-file', '-f', help='Optional file to output the JSON strings of '
              'the data collections. By default, it will be printed to stdout',
              type=click.File('w'), default='-', show_default=True)
def load_balance(model_json, result_sql, normalize, storage, output_file):
    """Get an array of DataCollection JSONs for a complete model's load balance.

    \b
    Args:
        model_json: Full path to a Model JSON file used for simulation.
        result_sql: Full path to an SQLite file that was generated by EnergyPlus.
    """
    try:
        # serialize the objects to Python
        with open(model_json) as json_file:
            data = json.load(json_file)
        model = Model.from_dict(data)

        # create the load balance object and output data to a JSON
        bal_obj = LoadBalance.from_sql_file(model, result_sql)
        balance = bal_obj.load_balance_terms(normalize, storage)
        output_file.write(json.dumps([data.to_dict() for data in balance]))
    except Exception as e:
        _logger.exception('Failed to construct load balance.\n{}'.format(e))
        sys.exit(1)
    else:
        sys.exit(0)
