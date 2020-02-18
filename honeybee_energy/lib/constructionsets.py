"""Collection of construction sets."""
from honeybee_energy.constructionset import ConstructionSet
from ._loadconstructionsets import _construction_sets, _construction_set_standards_dict

import honeybee_energy.lib.constructions as _c


# establish variables for the default construction sets used across the library
# and auto-generate construction sets if they were not loaded from default.idf
try:
    generic_construction_set = _construction_sets['Default Generic Construction Set']
except KeyError:
    generic_construction_set = ConstructionSet('Default Generic Construction Set')
    generic_construction_set.lock()
    _construction_sets['Default Generic Construction Set'] = generic_construction_set


# make lists of program types to look up items in the library
CONSTRUCTION_SETS = tuple(_construction_sets.keys()) + \
    tuple(_construction_set_standards_dict.keys())


def construction_set_by_name(construction_set_name):
    """Get a construction_set from the library given its name.

    Args:
        construction_set_name: A text string for the name of the ConstructionSet.
    """
    try:
        return _construction_sets[construction_set_name]
    except KeyError:
        try:  # search the extension data
            con_set_dict = _construction_set_standards_dict[construction_set_name]
            constrs = _constrs_from_set_dict(con_set_dict)
            return ConstructionSet.from_dict_abridged(con_set_dict, constrs)
        except KeyError:  # construction is nowhere to be found; raise an error
            raise ValueError('"{}" was not found in the construction set library.'.format(
                construction_set_name))


def _constrs_from_set_dict(con_set_dict):
    """Get a dictionary of constructions used in a ConstructionSetAbridged dictionary.
    """
    constrs = {}
    for key in con_set_dict:
        if isinstance(con_set_dict[key], dict):
            sub_dict = con_set_dict[key]
            for sub_key in sub_dict:
                if sub_key != 'type':
                    try:
                        constrs[sub_dict[sub_key]] = \
                            _c.opaque_construction_by_name(sub_dict[sub_key])
                    except ValueError:
                        constrs[sub_dict[sub_key]] = \
                            _c.window_construction_by_name(sub_dict[sub_key])
        elif key == 'shade_construction':
            constrs[con_set_dict[key]] = _c.shade_construction_by_name(con_set_dict[key])
        elif key == 'air_boundary_construction':
            constrs[con_set_dict[key]] = _c.opaque_construction_by_name(con_set_dict[key])
    return constrs
