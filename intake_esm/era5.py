""" Implementation for The ECMWF ERA5 Reanalyses data holdings """
import os

import pandas as pd

from .common import BaseSource, Collection, StorageResource, get_subset


class ERA5Collection(Collection):

    """ Defines ERA5 dataset collection

    Parameters
    ----------
    collection_spec : dict


    See Also
    --------
    intake_esm.core.ESMMetadataStoreCatalog
    intake_esm.cmip.CMIP5Collection
    intake_esm.cmip.CMIP6Collection
    intake_esm.cesm.CESMCollection
    intake_esm.mpige.MPIGECollection
    intake_esm.gmet.GMETCollection
    """

    def __init__(self, collection_spec):
        super(ERA5Collection, self).__init__(collection_spec)
        self.df = pd.DataFrame(columns=self.columns)

    def build(self):
        self._validate()
        for data_source, data_source_attrs in self.collection_spec['data_sources'].items():
            print(f'Working on data source: {data_source}')
            self.assemble_file_list(data_source, data_source_attrs)

        print(self.df.info())
        self.persist_db_file()
        return self.df

    def assemble_file_list(self, data_source, data_source_attrs):
        df_files = {}
        for location in data_source_attrs['locations']:
            res_key = ':'.join([location['name'], location['loc_type'], location['urlpath']])
            if res_key not in df_files:
                print(f'Getting file listing : {res_key}')

                exclude_dirs = location.get('exclude_dirs', [])
                file_extension = location.get('file_extension', '.nc')
                required_keys = ['urlpath', 'loc_type', 'direct_access']
                for key in required_keys:
                    if key not in location.keys():
                        raise ValueError(f'{key} must be specified in {self.collection_spec}')

                resource = resource = StorageResource(
                    urlpath=location['urlpath'],
                    loc_type=location['loc_type'],
                    exclude_dirs=exclude_dirs,
                    file_extension=file_extension,
                )

                df_files[res_key] = self._assemble_collection_df_files(
                    resource_key=res_key,
                    resource_type=location['loc_type'],
                    direct_access=location['direct_access'],
                    filelist=resource.filelist,
                )

        for res_key, df_f in df_files.items():
            self.df = pd.concat([df_f, self.df], ignore_index=True, sort=False)

        # Reorder columns
        self.df = self.df[self.columns]

        # Remove duplicates
        self.df = self.df.drop_duplicates(
            subset=['resource', 'file_fullpath'], keep='last'
        ).reset_index(drop=True)

    def _assemble_collection_df_files(self, resource_key, resource_type, direct_access, filelist):
        """ Assemble file listing into a Pandas DataFrame."""
        entries = {key: [] for key in self.columns}

        if not filelist:
            return pd.DataFrame(entries)

        print(f'Building file database : {resource_key}')
        for f in filelist:
            try:
                basename = os.path.basename(f)
                fileparts = self._get_filename_parts(basename)
            except Exception:
                continue

            entries['resource'].append(resource_key)
            entries['resource_type'].append(resource_type)
            entries['direct_access'].append(direct_access)
            entries['time_range'].append(fileparts['time_range'])
            entries['local_table'].append(fileparts['local_table'])
            entries['stream'].append(fileparts['stream'])
            entries['level_type'].append(fileparts['level_type'])
            entries['data_type'].append(fileparts['data_type'])
            entries['parameter_id'].append(fileparts['parameter_id'])
            entries['parameter_type'].append(fileparts['parameter_type'])
            entries['grid'].append(fileparts['grid'])
            entries['file_basename'].append(basename)
            entries['file_dirname'].append(os.path.dirname(f) + '/')
            entries['file_fullpath'].append(f)

        return pd.DataFrame(entries)

    def _get_filename_parts(self, filename):
        """ Get file attributes from filename """
        fs = filename.split('.')
        keys = {}
        keys['stream'] = fs[1]
        keys['data_type'] = fs[2]
        if keys['data_type'] == 'invariant':
            keys['level_type'] = None
        else:
            keys['level_type'] = fs[3]

        if keys['data_type'] == 'an':
            keys['parameter_type'] = 'instan'

        elif keys['data_type'] == 'fc':
            keys['parameter_type'] = fs[4]

        else:
            keys['parameter_type'] = None

        ecmwf_params = fs[-4].split('_')
        if len(ecmwf_params) == 3:
            keys['local_table'] = ecmwf_params[0]
            keys['parameter_id'] = ecmwf_params[1]
            keys['parameter_short_name'] = ecmwf_params[2]

        else:
            keys['local_table'] = None
            keys['parameter_id'] = None
            keys['parameter_short_name'] = None

        keys['grid'] = fs[-3]
        keys['time_range'] = fs[-2].replace('_', '-')
        return keys


class ERA5Source(BaseSource):
    name = 'era5'
    partition_access = True
