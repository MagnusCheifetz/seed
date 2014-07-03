"""
:copyright: (c) 2014 Building Energy Inc
:license: BSD 3-Clause, see LICENSE for more details.
"""
#!/usr/bin/env python
# encoding: utf-8
"""
urls/main.py

Copyright (c) 2013 Building Energy. All rights reserved.
"""

from django.conf.urls import patterns, url

urlpatterns = patterns(
    'seed.views.main',
    # template routes
    url(r'^$', 'home', name='home'),
    url(r'^admin/$', 'admin', name='admin'),

    # ajax routes
    url(
        r'^get_buildings_for_user/$',
        'get_buildings_for_user',
        name='get_buildings_for_user'
    ),
    url(
        r'^get_total_number_of_buildings_for_user/$',
        'get_total_number_of_buildings_for_user',
        name='get_total_number_of_buildings_for_user'
    ),
    url(r'^get_building/$', 'get_building', name='get_building'),
    url(
        r'^get_datasets_count/$',
        'get_datasets_count',
        name='get_datasets_count'
    ),
    url(r'^search_buildings/$', 'search_buildings', name='search_buildings'),
    url(
        r'^search_PM_buildings/$',
        'search_PM_buildings',
        name='search_PM_buildings'
    ),
    url(r'^get_PM_building/$', 'get_PM_building', name='get_PM_building'),
    url(
        r'^get_PM_building_matches/$',
        'get_PM_building_matches',
        name='get_PM_building_matches'
    ),
    url(
        r'^get_default_columns/$',
        'get_default_columns',
        name='get_default_columns'
    ),
    url(
        r'^set_default_columns/$',
        'set_default_columns',
        name='set_default_columns'
    ),
    url(r'^get_columns/$', 'get_columns', name='get_columns'),
    url(r'^save_match/$', 'save_match', name='save_match'),
    url(r'^save_raw_data/$', 'save_raw_data', name='save_raw_data'),
    url(
        r'^get_PM_filter_by_counts/$',
        'get_PM_filter_by_counts',
        name='get_PM_filter_by_counts'
    ),
    url(r'^create_dataset/$', 'create_dataset', name='create_dataset'),
    url(r'^get_datasets/$', 'get_datasets', name='get_datasets'),
    url(r'^get_dataset/$', 'get_dataset', name='get_dataset'),
    url(r'^get_import_file/$', 'get_import_file', name='get_import_file'),
    url(r'^delete_file/$', 'delete_file', name='delete_file'),
    url(r'^delete_dataset/$', 'delete_dataset', name='delete_dataset'),
    url(r'^update_dataset/$', 'update_dataset', name='update_dataset'),
    url(r'^update_building/$', 'update_building', name='update_building'),
    # New MCM endpoints
    url(
        r'^get_column_mapping_suggestions/$',
        'get_column_mapping_suggestions',
        name='get_column_mapping_suggestions'
    ),
    url(
        r'^get_raw_column_names/$',
        'get_raw_column_names',
        name='get_raw_column_names'
    ),
    url(
        r'^get_first_five_rows/$',
        'get_first_five_rows',
        name='get_first_five_rows'
    ),
    url(
        r'^save_column_mappings/$',
        'save_column_mappings',
        name='save_column_mappings'
    ),
    url(r'^start_mapping/$', 'start_mapping', name='start_mapping'),
    url(r'^remap_buildings/$', 'remap_buildings', name='remap_buildings'),
    url(
        r'^start_system_matching/$',
        'start_system_matching',
        name='start_system_matching'
    ),
    url(r'^progress/$', 'progress', name='progress'),

    # project urls

    # exporter routes
    url(r'^export_buildings/$', 'export_buildings', name='export_buildings'),
    url(
        r'^export_buildings/progress/$',
        'export_buildings_progress',
        name='export_buildings_progress'
    ),
    url(
        r'^export_buildings/download/$',
        'export_buildings_download',
        name='export_buildings_download'
    ),

    # test urls
    url(r'^angular_js_tests/$', 'angular_js_tests', name='angular_js_tests'),


    # org
    url(
        r'^delete_organization_buildings/$',
        'delete_organization_buildings',
        name='delete_organization_buildings'
    ),
)
