/**
 * :copyright: (c) 2014 Building Energy Inc
 * :license: BSD 3-Clause, see LICENSE for more details.
 */
/**
 * AngularJS app 'BE.seed' for SEED SPA
 */

angular.module('BE.seed.angular_dependencies', [
    'ngRoute',
    'ngCookies'
    ]);
angular.module('BE.seed.vendor_dependencies', [
    'ui.bootstrap',
    'ui.tree'
    ]);
angular.module('BE.seed.controllers', [
    'BE.seed.controller.accounts',
    'BE.seed.controller.admin',
    'BE.seed.controller.buiding_detail',
    'BE.seed.controller.buiding_list',
    'BE.seed.controller.concat_modal',
    'BE.seed.controller.create_organization_modal',
    'BE.seed.controller.custom_view_modal',
    'BE.seed.controller.data_upload_modal',
    'BE.seed.controller.dataset',
    'BE.seed.controller.dataset_detail',
    'BE.seed.controller.edit_label_modal',
    'BE.seed.controller.edit_project_modal',
    'BE.seed.controller.existing_members_modal',
    'BE.seed.controller.export_modal',
    'BE.seed.controller.mapping',
    'BE.seed.controller.matching',
    'BE.seed.controller.matching_detail',
    'BE.seed.controller.members',
    'BE.seed.controller.menu',
    'BE.seed.controller.new_member_modal',
    'BE.seed.controller.organization',
    'BE.seed.controller.organization_settings',
    'BE.seed.controller.project'
    ]);
angular.module('BE.seed.filters', [
    'district',
    'fromNow',
    'ignoremap',
    'stripImportPrefix',
    'titleCase',
    'typedNumber'
    ]);
angular.module('BE.seed.directives', [
    'beEnter',
    'beUploader',
    'beLabel'
    ]);
angular.module('BE.seed.services', [
    'BE.seed.service.auth',
    'BE.seed.service.building',
    'BE.seed.service.dataset',
    'BE.seed.service.export',
    'BE.seed.service.mapping',
    'BE.seed.service.matching',
    'BE.seed.service.organization',
    'BE.seed.service.project',
    'BE.seed.service.uploader',
    'BE.seed.service.user',
    'mappingValidatorService',
    'BE.seed.service.search'
    ]);

var SEED_app = angular.module('BE.seed', [
    'BE.seed.angular_dependencies',
    'BE.seed.vendor_dependencies',
    'BE.seed.filters',
    'BE.seed.directives',
    'BE.seed.services',
    'BE.seed.controllers'
], ['$interpolateProvider', function ($interpolateProvider) {
        $interpolateProvider.startSymbol("{$");
        $interpolateProvider.endSymbol("$}");
    }]
);

/**
 * Adds the Django CSRF token to all $http requests
 */
SEED_app.run([
  '$http',
  '$cookies',
  function ($http, $cookies) {
    $http.defaults.headers.common['X-CSRFToken'] = $cookies.csrftoken;
    BE.csrftoken = $cookies.csrftoken;
    $http.defaults.headers.post['X-CSRFToken'] = $cookies.csrftoken;
    $http.defaults.xsrfCookieName = 'csrftoken';
    $http.defaults.xsrfHeaderName = 'X-CSRFToken';
  }
]);

/**
 * url routing declaration for SEED
 */
SEED_app.config(['$routeProvider', function ($routeProvider) {

    var static_url = BE.urls.STATIC_URL;

    $routeProvider
        .when('/', {
            templateUrl: static_url + 'seed/partials/home.html'
        })
        .when('/projects', {
            controller: 'project_list_controller',
            templateUrl: static_url + 'seed/partials/projects.html',
            resolve: {
                'projects_payload': ['project_service', function(project_service) {
                    return project_service.get_projects();
                }]
            }
        })
        .when('/projects/:project_id', {
            controller: 'building_list_controller',
            templateUrl: static_url + 'seed/partials/project_detail.html',
            resolve: {
                'search_payload': ['building_services', '$route', function(building_services, $route){
                    var params = angular.copy($route.current.params);
                    var project_slug = params.project_id;
                    delete(params.project_id);
                    params.project__slug = project_slug;
                    var q = params.q || "";
                    // params: (query, number_per_page, page_number, order_by, sort_reverse, other_params, project_id, project_slug) 
                    return building_services.search_buildings(q, 10, 1, "", false, params, null, project_slug);
                }],
                'default_columns': ['user_service', function(user_service){
                    return user_service.get_default_columns();
                }],
                'all_columns': ['building_services', '$route', function(building_services, $route) {
                    var params = angular.copy($route.current.params);
                    var project_slug = params.project_id;
                    return building_services.get_columns(true, project_slug);
                }],
                'project_payload': ['$route', 'project_service', function($route, project_service) {
                    var params = angular.copy($route.current.params);
                    var project_slug = params.project_id;
                    return project_service.get_project(project_slug);
                }]
            }

        })
        .when('/projects/:project_id/:building_id', {
            controller: 'building_detail_controller',
            resolve: {
                'building_payload': ['building_services', '$route', function(building_services, $route){
                    // load `get_building` before page is loaded to avoid
                    // page flicker. 
                    // todo:
                    //  preload project here.
                    var building_id = $route.current.params.building_id;
                    return building_services.get_building(building_id);
                }],
                'all_columns': ['building_services', function(building_services) {
                    return building_services.get_columns(false);
                }]
            },
            templateUrl: static_url + 'seed/partials/building_detail.html'
        })
        .when('/buildings', {
            controller: 'building_list_controller',
            templateUrl: static_url + 'seed/partials/buildings.html',
            resolve: {
                'search_payload': ['building_services', '$route', function(building_services, $route){
                    var params = $route.current.params;
                    var q = params.q || "";
                    // params: (query, number_per_page, page_number, order_by, sort_reverse, other_params, project_id) 
                    return building_services.search_buildings(q, 10, 1, "", false, params, null);
                }],
                'default_columns': ['user_service', function(user_service){
                    return user_service.get_default_columns();
                }],
                'all_columns': ['building_services', function(building_services) {
                    return building_services.get_columns(false);
                }],
                'project_payload': function() {
                    return {
                        'project': {}
                    };
                }
            }
        })
        .when('/buildings/:building_id', {
            controller: 'building_detail_controller',
            templateUrl: static_url + 'seed/partials/building_detail.html',
            resolve: {
                'building_payload': ['building_services', '$route', function(building_services, $route){
                    // load `get_building` before page is loaded to avoid
                    // page flicker. 
                    var building_id = $route.current.params.building_id;
                    return building_services.get_building(building_id);
                }],
                'all_columns': ['building_services', function(building_services) {
                    return building_services.get_columns(false);
                }]
            }
        })
        .when('/data/mapping/:importfile_id', {
            controller: 'mapping_controller',
            templateUrl: static_url + 'seed/partials/mapping.html',
            resolve: {
                'import_file_payload': ['dataset_service', '$route', function(dataset_service, $route){
                    var importfile_id = $route.current.params.importfile_id;
                    return dataset_service.get_import_file(importfile_id);
                }],
                'suggested_mappings_payload': ['mapping_service', '$route', function(mapping_service, $route){
                    var importfile_id = $route.current.params.importfile_id;
                    return mapping_service.get_column_mapping_suggestions(
                        importfile_id
                    );
                }],
                'raw_columns_payload': ['mapping_service', '$route', function(mapping_service, $route){
                    var importfile_id = $route.current.params.importfile_id;
                    return mapping_service.get_raw_columns(
                        importfile_id
                    );
                }],
                'first_five_rows_payload': ['mapping_service', '$route', function(mapping_service, $route){
                    var importfile_id = $route.current.params.importfile_id;
                    return mapping_service.get_first_five_rows(
                        importfile_id
                    );
                }],
                'all_columns': ['building_services', function(building_services) {
                    return building_services.get_columns(false);
                }],
                'auth_payload': ['auth_service', '$q', 'user_service', function(auth_service, $q, user_service) {
                    var organization_id = user_service.get_organization().id;
                    return auth_service.is_authorized(organization_id, ['requires_member'])
                    .then(function (data) {
                        if (data.auth.requires_member){
                            return data;
                        } else {
                            return $q.reject("not authorized");
                        }
                    }, function (data) {
                        return $q.reject(data.message);
                    });
                }]
            }
        })
        .when('/data/matching/:importfile_id', {
            controller: 'matching_controller',
            templateUrl: static_url + 'seed/partials/matching.html',
            resolve: {
                'import_file_payload': ['dataset_service', '$route', function(dataset_service, $route){
                    var importfile_id = $route.current.params.importfile_id;
                    return dataset_service.get_import_file(importfile_id);
                }],
                'buildings_payload': ['building_services', '$route', function(building_services, $route){
                    var importfile_id = $route.current.params.importfile_id;
                    return building_services.search_matching_buildings(
                        "", 10, 1, "", false, {}, importfile_id);
                }],
                'default_columns': ['user_service', function(user_service){
                    return user_service.get_default_columns();
                }],
                'all_columns': ['building_services', function(building_services) {
                    return building_services.get_columns(false);
                }],
                'auth_payload': ['auth_service', '$q', 'user_service', function(auth_service, $q, user_service) {
                    var organization_id = user_service.get_organization().id;
                    return auth_service.is_authorized(organization_id, ['requires_member'])
                    .then(function (data) {
                        if (data.auth.requires_member){
                            return data;
                        } else {
                            return $q.reject("not authorized");
                        }
                    }, function (data) {
                        return $q.reject(data.message);
                    });
                }]
            }
        })
        .when('/data/:dataset_id', {
            controller: 'dataset_detail_controller',
            templateUrl: static_url + 'seed/partials/dataset_detail.html',
            resolve: {
                'dataset_payload': ['dataset_service', '$route', function(dataset_service, $route){
                    var dataset_id = $route.current.params.dataset_id;
                    return dataset_service.get_dataset(dataset_id);
                }],
                'auth_payload': ['auth_service', '$q', 'user_service', function(auth_service, $q, user_service) {
                    var organization_id = user_service.get_organization().id;
                    return auth_service.is_authorized(organization_id, ['requires_member'])
                    .then(function (data) {
                        if (data.auth.requires_member){
                            return data;
                        } else {
                            return $q.reject("not authorized");
                        }
                    }, function (data) {
                        return $q.reject(data.message);
                    });
                }]
            }
        })
        .when('/data', {
            controller: 'dataset_list_controller',
            templateUrl: static_url + 'seed/partials/dataset_list.html',
            resolve: {
                'datasets_payload': ['dataset_service', '$route', function(dataset_service, $route){
                    return dataset_service.get_datasets();
                }],
                'auth_payload': ['auth_service', '$q', 'user_service', function(auth_service, $q, user_service) {
                    var organization_id = user_service.get_organization().id;
                    return auth_service.is_authorized(organization_id, ['requires_member'])
                    .then(function (data) {
                        if (data.auth.requires_member){
                            return data;
                        } else {
                            return $q.reject("not authorized");
                        }
                    }, function (data) {
                        return $q.reject(data.message);
                    });
                }]
            }
        })
        .when('/feedback', {
            templateUrl: static_url + 'seed/partials/feedback.html'
        })
        .when('/accounts', {
            controller: 'accounts_controller',
            templateUrl: static_url + 'seed/partials/accounts.html',
            resolve: {
                'organization_payload': ['organization_service', function (organization_service) {
                    return organization_service.get_organizations();
                }]
            }
        })
        .when('/accounts/:organization_id', {
            controller: 'settings_controller',
            templateUrl: static_url + 'seed/partials/settings.html',
            resolve: {
                'all_columns': ['building_services', function(building_services) {
                    return building_services.get_columns(false);
                }],
                'organization_payload': ['organization_service', '$route', function(organization_service, $route) {
                    var organization_id = $route.current.params.organization_id;
                    return organization_service.get_organization(organization_id);
                }],
                'query_threshold_payload': ['organization_service', '$route', function(organization_service, $route) {
                    var organization_id = $route.current.params.organization_id;
                    return organization_service.get_query_threshold(organization_id);
                }],
                'shared_fields_payload': ['organization_service', '$route', function(organization_service, $route) {
                    var organization_id = $route.current.params.organization_id;
                    return organization_service.get_shared_fields(organization_id);
                }],
                'auth_payload': ['auth_service', '$route', '$q', function(auth_service, $route, $q) {
                    var organization_id = $route.current.params.organization_id;
                    return auth_service.is_authorized(organization_id, ['requires_owner'])
                    .then(function (data) {
                        if (data.auth.requires_owner){
                            return data;
                        } else {
                            return $q.reject("not authorized");
                        }
                    }, function (data) {
                        return $q.reject(data.message);
                    });
                }]
            }
        })
        .when('/accounts/:organization_id/sub_org', {
            controller: 'organization_controller',
            templateUrl: static_url + 'seed/partials/sub_org.html',
            resolve: {
                'users_payload': ['organization_service', '$route', function (organization_service, $route) {
                    var organization_id = $route.current.params.organization_id;
                    return organization_service.get_organization_users({'org_id': organization_id});
                }],
                'organization_payload': ['organization_service', '$route', '$q', function(organization_service, $route, $q) {
                    var organization_id = $route.current.params.organization_id;
                    return organization_service.get_organization(organization_id)
                    .then(function (data){
                        if (data.organization.is_parent) {
                            return data;
                        } else {
                            return $q.reject("Your page could not be located!");
                        }
                    });
                }],
                'auth_payload': ['auth_service', '$route', '$q', function(auth_service, $route, $q) {
                    var organization_id = $route.current.params.organization_id;
                    return auth_service.is_authorized(organization_id, ['requires_owner'])
                    .then(function (data) {
                        if (data.auth.requires_owner){
                            return data;
                        } else {
                            return $q.reject("not authorized");
                        }
                    }, function (data) {
                        return $q.reject(data.message);
                    });
                }]
            }
        })
        .when('/accounts/:organization_id/members', {
            controller: 'members_controller',
            templateUrl: static_url + 'seed/partials/members.html',
            resolve: {
                'users_payload': ['organization_service', '$route', function (organization_service, $route) {
                    var organization_id = $route.current.params.organization_id;
                    return organization_service.get_organization_users({'org_id': organization_id});
                }],
                'organization_payload': ['organization_service', '$route', function(organization_service, $route) {
                    var organization_id = $route.current.params.organization_id;
                    return organization_service.get_organization(organization_id);
                }],
                'auth_payload': ['auth_service', '$route', '$q', function(auth_service, $route, $q) {
                    var organization_id = $route.current.params.organization_id;
                    return auth_service.is_authorized(organization_id, ['can_invite_member', 'can_remove_member', 'requires_owner', 'requires_member'])
                    .then(function (data) {
                        if (data.auth.requires_member){
                            return data;
                        } else {
                            return $q.reject("not authorized");
                        }
                    }, function (data) {
                        return $q.reject(data.message);
                    });
                }]
            }
        })
        .otherwise({ redirectTo: '/' });

}]);

/**
 * whitelist needed to load html partials from Amazon AWS S3 
 * defaults to 'self' otherwise
 */
SEED_app.config([
  '$sceDelegateProvider',
  function ($sceDelegateProvider) {
    $sceDelegateProvider.resourceUrlWhitelist([
      'self',
      '**'
    ]);
  }
]);

SEED_app.config([
    '$httpProvider',
    function($httpProvider) {
    $httpProvider.defaults.headers.common['X-Requested-With'] = 'XMLHttpRequest';
}]);

/**
 * creates the object 'urls' which can be injected into a service, controller, etc.
 */
SEED_app.constant('urls', {
    search_buildings: BE.urls.search_buildings_url,
    search_PM_buildings: BE.urls.search_PM_buildings_url,
    get_PM_building: BE.urls.get_PM_building_url,
    get_PM_building_matches: BE.urls.get_PM_building_matches_url,
    save_match: BE.urls.save_match_url,
    seed_home: BE.urls.seed_home,
    update_building: BE.urls.update_building,
    static_url: BE.urls.STATIC_URL
});
SEED_app.constant('generated_urls', window.BE.app_urls);