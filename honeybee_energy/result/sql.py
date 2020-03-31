# coding=utf-8
"""Module for parsing EnergyPlus SQLite result files into Ladybug DataCollections"""
from __future__ import division

import os
import sqlite3

import ladybug.datatype
from ladybug.dt import DateTime
from ladybug.location import Location
from ladybug.analysisperiod import AnalysisPeriod
from ladybug.header import Header
from ladybug.datacollection import HourlyContinuousCollection, DailyCollection, \
    MonthlyCollection


class SQLiteResult(object):
    """Object for parsing EnergyPlus SQLite result files into Ladybug DataCollections.

    Args:
        file_path: Full path to an SQLite file that was generated by EnergyPlus.

    Properties:
        * file_path
        * location
    """
    _interval_codes = ('Timestep', 'Hourly', 'Daily', 'Monthly', 'Annual')

    def __init__(self, file_path):
        """Initialize SQLiteResult"""
        assert os.path.isfile(file_path), 'No file was found at {}'.format(file_path)
        assert file_path.endswith(('.sql', '.db', '.sqlite')), \
            '{} is not an SQL file ending in .sql or .db.'.format(file_path)
        self._file_path = file_path
        self._location = None  # compute it as soon as it's requested

    @property
    def file_path(self):
        """Get the path to the .sql file."""
        return self._file_path

    @property
    def location(self):
        """Get a Ladybug Location object derived from the SQL data.
        
        This will be None if there was no AllSummary report requested from the
        simulation.
        """
        if not self._location:
            self._extract_location()
        return self._location

    def data_collections_by_output_name(self, output_name):
        """Get an array of Ladybug DataCollections for a specified output.

        Args:
            output_name: The name of an EnergyPlus output to be retrieved from
                the SQLite result file. This can also be an array of output names
                for which all data collections should be retrieved.

        Returns:
            An array of data collections of the requested output type. This will
            be an empty list if no output of the requested name was found in the
            file.
        """
        conn = sqlite3.connect(self.file_path)
        try:
            # extract all indices in the ReportDataDictionary with the output_name
            c = conn.cursor()
            if isinstance(output_name, str):
                c.execute('SELECT * FROM ReportDataDictionary WHERE Name=?',
                          (output_name,))
            else:
                c.execute('SELECT * FROM ReportDataDictionary WHERE Name IN {}'.format(
                    output_name))
            header_rows = c.fetchall()

            # if nothing was found, return an empty list
            if len(header_rows) == 0:
                conn.close()  # ensure connection is always closed
                return []

            # extract all data of the relevant type from ReportData
            rel_indices = tuple(row[0] for row in header_rows)
            if len(rel_indices) == 1:
                c.execute('SELECT Value, TimeIndex FROM ReportData WHERE '
                          'ReportDataDictionaryIndex=?', rel_indices)
            else:
                c.execute('SELECT Value, TimeIndex FROM ReportData WHERE '
                        'ReportDataDictionaryIndex IN {}'.format(rel_indices))
            data = c.fetchall()
            conn.close()  # ensure connection is always closed
        except Exception as e:
            conn.close()  # ensure connection is always closed
            raise Exception(str(e))

        # get the analysis period and the reporting frequency from the time table
        st_time, end_time = data[0][1], data[-1][1]
        run_period, reporting_frequency = self._extract_run_period(st_time, end_time)

        # create the header objects to be used for the resulting data collections
        units = header_rows[0][-1] if header_rows[0][-1] != 'J' else 'kWh'
        data_type = self._data_type_from_unit(units)
        headers = []
        for row in header_rows:
            obj_type = row[3] if 'Surface' not in output_name else 'Surface'
            metadata = {'type': row[6], obj_type: row[5]}
            headers.append(Header(data_type, units, run_period, metadata))

        # format the data such that we have one list for each of the header rows
        n_lists = len(header_rows)
        if units == 'kWh':
            all_values = self._clean_and_convert_timeseries_data(data, n_lists)
        else:
            all_values = self._clean_timeseries_data(data, n_lists)

        # create the final data collections
        data_colls = []
        if reporting_frequency == 'Hourly' or isinstance(reporting_frequency, int):
            for head, values in zip(headers, all_values):
                data_colls.append(HourlyContinuousCollection(head, values))
        elif reporting_frequency == 'Daily':
            for head, values in zip(headers, all_values):
                data_colls.append(DailyCollection(
                    head, values, head.analysis_period.doys_int))
        elif reporting_frequency == 'Monthly':
            for head, values in zip(headers, all_values):
                data_colls.append(MonthlyCollection(
                    head, values, head.analysis_period.months_int))
        else:  # Annual data; just return the values as they are
            return all_values

        return data_colls
    
    def tablular_data_by_name(self, table_name):
        """Get all the data within a table of a Summary Report using the table name.

        Args:
            table_name: Text string for the name of a table within a summary
                report. (eg. 'General').
        """
        conn = sqlite3.connect(self.file_path)
        try:
            # extract the data from the General table in AllSummary
            c = conn.cursor()
            c.execute('SELECT Value FROM TabularDataWithStrings '
                      'WHERE TableName=?', (table_name,))
            table_data = c.fetchall()
            conn.close()  # ensure connection is always closed
        except Exception as e:
            conn.close()  # ensure connection is always closed
            raise Exception(str(e))
        return table_data

    def _extract_location(self):
        """Extract a Location object from the SQLite file."""
        # extract all of the data from the General table in AllSummary
        general = self.tablular_data_by_name('General')
        if general == []:
            return

        # convert the extracted data into a Location object
        split_id = general[2][0].split(' ')
        city = ' '.join(split_id[:-2])
        source = split_id[-2]
        station_id = split_id[-1].split('=')[-1]
        self._location = Location(
            city=city, source=source, station_id=station_id,
            latitude=general[3][0], longitude=general[4][0],
            time_zone=general[6][0], elevation=general[5][0])

    def _extract_run_period(self, st_time, end_time):
        """Extract the run period object and frequency from the SQLite file.
        
        Args:
            st_time: Index for the start time of the data.
            end_time: Index for the end time of the data.

        Returns:
            A tuple with run_period and reporting_frequency.
        """
        conn = sqlite3.connect(self.file_path)
        try:
            # extract all of the data from the Time table
            c = conn.cursor()
            c.execute('SELECT * FROM Time WHERE TimeIndex=?', (st_time,))
            start = c.fetchone()
            c.execute('SELECT * FROM Time WHERE TimeIndex=?', (end_time,))
            end = c.fetchone()
            conn.close()  # ensure connection is always closed
        except Exception as e:
            conn.close()  # ensure connection is always closed
            raise Exception(str(e))

        # set the reporting frequency by the interval type
        interval_typ = start[8]
        if interval_typ <= 1:
            min_per_step = start[7]
            aper_timestep = int(60 / min_per_step)
            reporting_frequency = aper_timestep
        else:
            reporting_frequency = self._interval_codes[interval_typ]
            aper_timestep = 1
            min_per_step = 60

        # convert the extracted data into an AnalysisPeriod object
        leap_year = True if start[1] % 4 == 0 else False
        if reporting_frequency == 'Monthly':
            st_date = DateTime(start[2], 1, 0)
        else:
            st_date = DateTime(start[2], start[3], 0)
        end_date = DateTime(end[2], end[3], 0)
        end_date = end_date.add_minute(1440 - min_per_step)
        run_period = AnalysisPeriod(
            st_date.month, st_date.day, st_date.hour, end_date.month, end_date.day,
            end_date.hour, aper_timestep, leap_year)

        return run_period, reporting_frequency

    def _check_desdays_in_report(self):
        """Check the Simulation Control object to see if design days are reported."""
        sim_control = self.tablular_data_by_name('Simulation Control')
        if sim_control == [] or sim_control[3][0] == 'No':
            return True
        return False

    @staticmethod
    def _data_type_from_unit(from_unit):
        """Get a Ladybug DataType object instance from a unit abbreviation.
        
        The returned object will be the base type (eg. Tmperture, Energy, etc.).
        """
        for key in ladybug.datatype.UNITS:
            if from_unit in ladybug.datatype.UNITS[key]:
                return ladybug.datatype.TYPESDICT[key]()

    @staticmethod
    def _clean_timeseries_data(data, n_lists):
        """Clean timeseries data that has been retrived from the SQL file."""
        all_values = []
        for i in range(0, len(data), n_lists):
            all_values.append([val[0] for val in data[i:i + n_lists]])
        return zip(*all_values)

    @staticmethod
    def _clean_and_convert_timeseries_data(data, n_lists):
        """Clean data that retrived from the SQL file + convert it to kWh."""
        all_values = []
        for i in range(0, len(data), n_lists):
            all_values.append([val[0] / 3600000. for val in data[i:i + n_lists]])
        return zip(*all_values)

    def ToString(self):
        """Overwrite .NET ToString."""
        return self.__repr__()

    def __repr__(self):
        return 'Energy SQLiteResult: {}'.format(self.file_path)
