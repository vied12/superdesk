define([
    'angular',
    'require',
    './controllers/list',
    './controllers/upload',
    './archive-widget/archive',
    './directives'
], function(angular, require) {
    'use strict';

    SpikeService.$inject = ['$location', 'api', 'notify', 'gettext'];
    function SpikeService($location, api, notify, gettext) {
        var SPIKE_RESOURCE = 'archive_spike',
            UNSPIKE_RESOURCE = 'archive_unspike';

        /**
         * Spike given item.
         *
         * @param {Object} item
         */
        this.spike = function spike(item) {
            return api.update(SPIKE_RESOURCE, item, {state: 'spiked'})
                .then(function() {
                    if ($location.search()._id === item._id) {
                        $location.search('_id', null);
                    }
                    item.actioning.spike = false;
                }, function(response) {
                    item.error = response;
                    item.actioning.spike = false;
                });
        };

        /**
         * Unspike given item.
         *
         * @param {Object} item
         */
        this.unspike = function unspike(item) {
            return api.update(UNSPIKE_RESOURCE, item, {})
                .then(function() {
                    item.actioning.unspike = false;
                }, function(response) {
                    item.error = response;
                    item.actioning.unspike = false;
                });
        };
    }

    return angular.module('superdesk.archive', [
        'superdesk.search',
        require('./directives').name,
        'superdesk.dashboard',
        'superdesk.widgets.archive'
    ])

        .service('spike', SpikeService)

        .config(['superdeskProvider', function(superdesk) {
            superdesk
                .activity('/workspace/content', {
                    label: gettext('Workspace'),
                    priority: 100,
                    controller: require('./controllers/list'),
                    templateUrl: require.toUrl('./views/list.html'),
                    topTemplateUrl: require.toUrl('../superdesk-dashboard/views/workspace-topnav.html'),
                    filters: [
                        {action: 'view', type: 'content'}
                    ],
                    privileges: {archive: 1}
                })
                .activity('upload.media', {
                    label: gettext('Upload media'),
                    modal: true,
                    cssClass: 'upload-media responsive-popup',
                    controller: require('./controllers/upload'),
                    templateUrl: require.toUrl('./views/upload.html'),
                    filters: [
                        {action: 'upload', type: 'media'}
                    ],
                    privileges: {archive: 1}
                })
                .activity('spike', {
                    label: gettext('Spike Item'),
                    icon: 'remove',
                    monitor: 'true',
                    controller: ['spike', 'data', function spikeActivity(spike, data) {
                        return spike.spike(data.item);
                    }],
                    filters: [{action: 'list', type: 'archive'}],
                    action: 'spike'
                })
                .activity('unspike', {
                    label: gettext('Unspike Item'),
                    icon: 'revert',
                    monitor: 'true',
                    controller: ['spike', 'data', function unspikeActivity(spike, data) {
                        return spike.unspike(data.item);
                    }],
                    filters: [{action: 'list', type: 'spike'}],
                    action: 'unspike'
                })
                .activity('archiveContent', {
                    label: gettext('Fetch'),
                    icon: 'archive',
                    monitor: 'true',
                    controller: ['api', 'data', 'desks', function(api, data, desks) {
                        api.archiveIngest.create({
                            guid: data.item.guid,
                            desk: desks.getCurrentDeskId()
                        })
                        .then(function(archiveItem) {
                            data.item.task_id = archiveItem.task_id;
                            data.item.created = archiveItem.created;
                            data.item.actioning.archiveContent = false;
                        }, function(response) {
                            data.item.error = response;
                            data.item.actioning.archiveContent = false;
                        });
                    }],
                    filters: [{action: 'list', type: 'archive'}],
                    action: 'fetch_as_from_content'
                });
        }])

        .config(['apiProvider', function(apiProvider) {
            apiProvider.api('notification', {
                type: 'http',
                backend: {
                    rel: 'notification'
                }
            });
            apiProvider.api('archive', {
                type: 'http',
                backend: {
                    rel: 'archive'
                }
            });
            apiProvider.api('archiveMedia', {
                type: 'http',
                backend: {
                    rel: 'archive_media'
                }
            });
        }]);
});
