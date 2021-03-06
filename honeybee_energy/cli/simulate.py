"""honeybee energy simulation running commands."""

try:
    import click
except ImportError:
    raise ImportError(
        'click is not installed. Try `pip install . [cli]` command.'
    )

from honeybee_energy.simulation.parameter import SimulationParameter
from honeybee_energy.run import measure_compatible_model_json, to_openstudio_osw, \
    run_osw, run_idf, output_energyplus_files
from honeybee.config import folders
from ladybug.futil import preparedir

import sys
import os
import logging
import json

_logger = logging.getLogger(__name__)


@click.group(help='Commands for simulating Honeybee JSON files in EnergyPlus.')
def simulate():
    pass


@simulate.command('model')
@click.argument('model-json')
@click.argument('epw-file')
@click.option('--sim-par-json', help='Full path to a honeybee energy SimulationParameter'
              ' JSON that describes all of the settings for the simulation.',
              default=None, show_default=True)
@click.option('--base-osw', help='Full path to an OSW JSON be used as the base for '
              'the execution of the OpenStuduo CLI. This can be used to add '
              'measures in the workflow.', default=None, show_default=True)
@click.option('--folder', help='Folder on this computer, into which the IDF and result'
              'files will be written. If None, the files will be output to the honeybee '
              'default simulation folder and placed in a project folder with the same '
              'name as the model_json.', default=None, show_default=True)
@click.option('--check-model/--bypass-check', help='Flag to note whether the Model '
              'should be re-serialized to Python and checked before it is translated '
              'to .osm. The check is not needed if the model-json was expored directly '
              'from the honeybee-energy Python library.', default=True, show_default=True)
@click.option('--log-file', help='Optional log file to output the paths of the generated'
              ' files (osw, osm, idf, sql, zsz, rdd, html, err) if successfully '
              'created. By default the list will be printed out to stdout',
              type=click.File('w'), default='-', show_default=True)
def simulate_model(model_json, epw_file, sim_par_json, base_osw, folder,
                   check_model, log_file):
    """Simulate a Model JSON file in EnergyPlus.
    \n
    Args:
        model_json: Full path to a Model JSON file.\n
        epw_file: Full path to an .epw file.
    """
    try:
        # check that the model JSON and the EPW file is there
        assert os.path.isfile(model_json), \
            'No Model JSON file found at {}.'.format(model_json)
        assert os.path.isfile(epw_file), \
            'No EPW file found at {}.'.format(epw_file)
        # ddy variable that might get used later
        epw_folder, epw_file_name = os.path.split(epw_file)
        ddy_file = os.path.join(epw_folder, epw_file_name.replace('.epw', '.ddy'))

        # set the default folder to the default if it's not specified
        if folder is None:
            proj_name = os.path.basename(model_json).replace('.json', '')
            folder = os.path.join(
                folders.default_simulation_folder, proj_name, 'OpenStudio')
            preparedir(folder, remove_content=False)

        # process the simulation parameters and write new ones if necessary
        def write_sim_par(sim_par):
            """Write simulation parameter object to a JSON."""
            sim_par_dict = sim_par.to_dict()
            sp_json = os.path.abspath(os.path.join(folder, 'simulation_parameter.json'))
            with open(sp_json, 'w') as fp:
                json.dump(sim_par_dict, fp)
            return sp_json
        if sim_par_json is None:  # generate some default simulation parameters
            sim_par = SimulationParameter()
            sim_par.output.add_zone_energy_use()
            sim_par.output.add_hvac_energy_use()
            if os.path.isfile(ddy_file):
                sim_par.sizing_parameter.add_from_ddy_996_004(ddy_file)
            else:
                raise ValueError(
                    'No sim-par-json was input and there is no .ddy file next to '
                    'the .epw.\nAt least one of these two cirtieria must be satisfied '
                    'for a successful simulation.')
            sim_par_json = write_sim_par(sim_par)
        else:
            assert os.path.isfile(sim_par_json), \
                'No simulation parameter file found at {}.'.format(sim_par_json)
            with open(sim_par_json) as json_file:
                data = json.load(json_file)
            sim_par = SimulationParameter.from_dict(data)
            if len(sim_par.sizing_parameter.design_days) == 0 and os.path.isfile(ddy_file):
                sim_par.sizing_parameter.add_from_ddy_996_004(ddy_file)
                sim_par_json = write_sim_par(sim_par)
            elif len(sim_par.sizing_parameter.design_days) == 0:
                raise ValueError(
                    'No design days were found in the input sim-par-json and there is '
                    'no .ddy file next to the .epw.\nAt least one of these two cirtieria '
                    'must be satisfied for a successful simulation.')

        # run the Model re-serialization and check if specified
        if check_model:
            model_json = measure_compatible_model_json(model_json, folder)

        # Write the osw file to translate the model to osm
        osw = to_openstudio_osw(folder, model_json, sim_par_json,
                                base_osw=base_osw, epw_file=epw_file)

        # run the measure to translate the model JSON to an openstudio measure
        if osw is not None and os.path.isfile(osw):
            gen_files = [osw]
            if base_osw is None:  # separate the OS CLI run from the E+ run
                osm, idf = run_osw(osw)
                # run the resulting idf through EnergyPlus
                if idf is not None and os.path.isfile(idf):
                    gen_files.extend([osm, idf])
                    sql, eio, rdd, html, err = run_idf(idf, epw_file)
                    if err is not None and os.path.isfile(err):
                        gen_files.extend([sql, eio, rdd, html, err])
                    else:
                        raise Exception('Running EnergyPlus failed.')
                else:
                    raise Exception('Running OpenStudio CLI failed.')
            else:  # run the whole simulation with the OpenStudio CLI
                osm, idf = run_osw(osw, measures_only=False)
                if idf is not None and os.path.isfile(idf):
                    gen_files.extend([osm, idf])
                else:
                    raise Exception('Running OpenStudio CLI failed.')
                sql, eio, rdd, html, err = output_energyplus_files(os.path.dirname(idf))
                if os.path.isfile(err):
                    gen_files.extend([sql, eio, rdd, html, err])
                else:
                    raise Exception('Running EnergyPlus failed.')
            log_file.write(json.dumps(gen_files))
        else:
            raise Exception('Writing OSW file failed.')
    except Exception as e:
        _logger.exception('Model simulation failed.\n{}'.format(e))
        sys.exit(1)
    else:
        sys.exit(0)
