"""
:copyright: (c) 2014 Building Energy Inc
:license: see LICENSE for more details.
"""
# system imports
import json

# django imports
from django.db import models
from django.core import serializers
from django.utils.translation import ugettext_lazy as _

# vendor imports
from autoslug import AutoSlugField

# provides created and modifed fields
from landing.models import SEEDUser as User
from django_extensions.db.models import TimeStampedModel
from djorm_pgjson.fields import JSONField
from djorm_expressions.models import ExpressionManager

from data_importer.models import ImportFile, ImportRecord

from mcm import mapper
from superperms.orgs.models import (
    Organization as SuperOrganization,
)

from seed.utils.time import convert_datestr


PROJECT_NAME_MAX_LENGTH = 255

# Represents the data source of a given BuildingSnapshot

ASSESSED_RAW = 0
PORTFOLIO_RAW = 1
ASSESSED_BS = 2
PORTFOLIO_BS = 3
COMPOSITE_BS = 4

SEED_DATA_SOURCES = (
    (ASSESSED_RAW, 'Assessed Raw'),
    (ASSESSED_BS, 'Assessed'),
    (PORTFOLIO_RAW, 'Portfolio Raw'),
    (PORTFOLIO_BS, 'Portfolio'),
    (COMPOSITE_BS, 'BuildingSnapshot'),
)


SYSTEM_MATCH = 1
USER_MATCH = 2
POSSIBLE_MATCH = 3


SEED_MATCH_TYPES = (
    (SYSTEM_MATCH, 'System Match'),
    (USER_MATCH, 'User Match'),
    (POSSIBLE_MATCH, 'Possible Match'),
)


SEARCH_CONFIDENCE_RANGES = {
    'low': 0.4,
    'medium': 0.75,
    'high': 1.0,
}


BS_VALUES_LIST = [
    'pk',  # needed for matching not to blow up
    'tax_lot_id',
    'pm_property_id',
    'custom_id_1',
    'address_line_1',
]


NATURAL_GAS = 1
ELECTRICITY = 2
FUEL_OIL = 3
FUEL_OIL_NO_1 = 4
FUEL_OIL_NO_2 = 5
FUEL_OIL_NO_4 = 6
FUEL_OIL_NO_5_AND_NO_6 = 7
DISTRICT_STEAM = 8
DISTRICT_HOT_WATER = 9
DISTRICT_CHILLED_WATER = 10
PROPANE = 11
LIQUID_PROPANE = 12
KEROSENE = 13
DIESEL = 14
COAL = 15
COAL_ANTHRACITE = 16
COAL_BITUMINOUS = 17
COKE = 18
WOOD = 19
OTHER = 20


ENERGY_TYPES = (
    (NATURAL_GAS, 'Natural Gas'),
    (ELECTRICITY, 'Electricity'),
    (FUEL_OIL, 'Fuel Oil'),
    (FUEL_OIL_NO_1, 'Fuel Oil No. 1'),
    (FUEL_OIL_NO_2, 'Fuel Oil No. 2'),
    (FUEL_OIL_NO_4, 'Fuel Oil No. 4'),
    (FUEL_OIL_NO_5_AND_NO_6, 'Fuel Oil No. 5 and No. 6'),
    (DISTRICT_STEAM, 'District Steam'),
    (DISTRICT_HOT_WATER, 'District Hot Water'),
    (DISTRICT_CHILLED_WATER, 'District Chilled Water'),
    (PROPANE, 'Propane'),
    (LIQUID_PROPANE, 'Liquid Propane'),
    (KEROSENE, 'Kerosene'),
    (DIESEL, 'Diesel'),
    (COAL, 'Coal'),
    (COAL_ANTHRACITE, 'Coal Anthracite'),
    (COAL_BITUMINOUS, 'Coal Bituminous'),
    (COKE, 'Coke'),
    (WOOD, 'Wood'),
    (OTHER, 'Other'),
)


KILOWATT_HOURS = 1
THERMS = 2

ENERGY_UNITS = (
    (KILOWATT_HOURS, 'kWh'),
    (THERMS, 'Therms'),
)

#
## Used in ``tasks.match_buildings``
###


def get_ancestors(building):
    """gets all the non-raw, non-composite ancestors of a building

       Recursive function to traverse the tree upward.
       source_type {
           2: ASSESSED_BS,
           3: PORTFOLIO_BS,
           4: COMPOSITE_BS
       }

       :param building: BuildingSnapshot inst.
       :returns: list of BuildingSnapshot inst., ancestors of building
    """
    ancestors = []
    parents = building.parents.filter(source_type__in=[2, 3, 4])
    ancestors.extend(parents.filter(source_type__in=[2, 3]))
    for p in parents:
        ancestors.extend(get_ancestors(p))
    return ancestors


def find_unmatched_building_values(import_file):
    """Get unmatched building snapshots' id info from an import file.

    :param import_file: ImportFile inst.

    :rtype: list of tuples, field values specified in BS_VALUES_LIST.

    NB: This does not return a queryset!

    """
    return BuildingSnapshot.objects.filter(
        ~models.Q(source_type__in=[COMPOSITE_BS, ASSESSED_RAW, PORTFOLIO_RAW]),
        match_type=None,
        import_file=import_file,
        canonical_building=None,
    ).values_list(*BS_VALUES_LIST)


def find_canonical_building_values(org):
    """Get all canonical building snapshots' id info for an organization.

    :param org: Organization inst.

    :rtype: list of tuples, field values specified in BS_VALUES_LIST
        for all canonical buildings related to an organization.

    NB: This does not return a queryset!

    """
    users = org.users.all()
    return BuildingSnapshot.objects.filter(
        pk__in=CanonicalBuilding.objects.filter(
            canonical_snapshot__import_file__import_record__owner__in=users
        ).values_list('canonical_snapshot_id')
    ).distinct().values_list(*BS_VALUES_LIST)


def obj_to_dict(obj):
    """serializes obj for a JSON friendly version
        tries to serialize JSONField

    """
    data = serializers.serialize('json', [obj, ])
    struct = json.loads(data)[0]
    response = struct['fields']
    response[u'id'] = response[u'pk'] = struct['pk']
    response[u'model'] = struct['model']
    # JSONField doesn't get serialized by `serialize`
    for f in obj._meta.fields:
        if type(f) == JSONField:
            e = getattr(obj, f.name)
            # postgres < 9.3 support
            while type(e) == unicode:
                e = json.loads(e)
            response[unicode(f.name)] = e
    return response


def get_sourced_attributes(snapshot):
    """Return all the attribute names that get sourced."""
    single_sources = []
    plural_sources = []
    for item in snapshot._meta.fields:
        if hasattr(snapshot, '{0}_source'.format(item.name)):
            single_sources.append(item.name)
        if hasattr(snapshot, '{0}_sources'.format(item.name)):
            plural_sources.append(item.name)

    return single_sources, plural_sources


def set_initial_sources(snapshot):
    """Sets the PK for the original sources to self."""
    single, plural = get_sourced_attributes(snapshot)
    for attr in single:
        # We set the attribute source to be itself.
        setattr(snapshot, '{0}_source'.format(attr), snapshot)

    for attr in plural:
        # We have to assume that it's a dict
        attrs = getattr(snapshot, attr, {})
        sources = getattr(snapshot, '{0}_sources', {})
        for k in attrs:
            sources[k] = snapshot.pk

        setattr(snapshot, '{0}_sources'.format(attr), sources)

    return snapshot


def get_or_create_canonical(b1, b2=None):
    """Gets most trusted Canonical Building.

    :param b1: BuildingSnapshot model type.
    :param b2: BuildingSnapshot model type.
    :rtype: CanonicalBuilding inst. Will contain PK.

    NB: preference is given to existing snapshots' Canonical link.

    """
    canon = b1.canonical_building
    if not canon and b2:
        canon = b2.canonical_building
    if not canon:
        canon = CanonicalBuilding.objects.create()

    return canon


def initialize_canonical_building(snapshot):
    """Called to create a Canonicalbuilding from a single snapshot.

    :param snapshot: BuidingSnapshot inst.

    """
    canon = get_or_create_canonical(snapshot)
    snapshot.canonical_building = canon
    snapshot.save()
    canon.canonical_snapshot = snapshot
    canon.save()


def clean_canonicals(b1, b2, new_snapshot):
    """Make sure that we don't leave dead limbs in our tree.

    :param b1: BuildingSnapshot, parent 1
    :param b2: BuildingSnapshot, parent 2
    :param new_snapshot: BuildingSnapshot, child.

    """
    latest_canon = new_snapshot.canonical_building
    for p in [b1, b2]:
        canon = p.canonical_building
        if canon and latest_canon and canon.pk != latest_canon.pk:
            canon.active = False
            canon.save()


def save_snapshot_match(
    b1_pk, b2_pk, confidence=None, user=None, match_type=None
):
    """Saves a match between two models as a new snapshot; updates Canonical.

    :param b1_pk: int, id for building snapshot.
    :param b2_pk: int, id for building snapshot.
    :param canonical: (optional) CanonicalBuilding inst; link to this.
    :param confidence: (optional) float, liklihood that two models are linked.
    :param user: (optional) User inst, last_modified_by for BuildingSnapshot.
    :rtype: BuildingSnapshot instance, post save.

    Determines which Canonical link should be used. If ``canonical`` is
    specified,
    we're probably changing a building's Canonical link, so use that Canonical
    Building. Otherwise, use the model we match against. If none exists,
    create it.

    Update mapped fields in the new snapshot, update canonical links.

    """
    from seed.mappings import mapper as seed_mapper

    # No point in linking the same building together.
    if b1_pk == b2_pk:
        return

    b1 = BuildingSnapshot.objects.get(pk=b1_pk)
    b2 = BuildingSnapshot.objects.get(pk=b2_pk)

    new_snapshot = BuildingSnapshot.objects.create()
    new_snapshot = seed_mapper.merge_building(
        new_snapshot,
        b1,
        b2,
        seed_mapper.get_building_attrs([b1, b2]),
        conf=confidence,
        match_type=match_type
    )

    clean_canonicals(b1, b2, new_snapshot)

    new_snapshot.last_modified_by = user

    new_snapshot.meters.add(*b1.meters.all())
    new_snapshot.meters.add(*b2.meters.all())
    new_snapshot.super_organization = b1.super_organization
    new_snapshot.super_organization = b2.super_organization

    new_snapshot.save()

    return new_snapshot


def unmatch_snapshot_tree(building_pk):
    """May or may not obviate ``unmatch_snapshot``. Experimental.

    :param building_pk: int - Primary Key for a BuildingSnapshot.

    .. warning::

        ``unmatch_snapshot_tree`` potentially modifies *years* of
        merged data. Anything decended from the ``building_pk`` will
        be deleted. The intent is to completely separate ``building_pk``'s
        influence on the resultant canonical_snapshot. The user is saying
        that these are separate entities afterall, yes?

    Basically, this function works by getting a merge order list of
    children from the perspective of ``building_pk`` and a list of parents
    from the perspective of leaf node in the child tree. We take the difference
    between these lists and call that the ``remaining_ancestors`` from which
    we reconstruct the merge tree for our CanonicalBuilding.

    ``building_pk`` either gets a reactivated CanonicalBuilding, or a new one.

    """
    snapshot = new_root = BuildingSnapshot.objects.get(pk=building_pk)
    children = snapshot.child_tree
    last_node = snapshot
    if children:
        last_node = children[-1]

    # If we're a leaf node, reset our unmatch to be one of the parents.
    # Assumes there are really only ever 2 parents at a time (e.g. it doesn't
    # matter which one we choose to unmerge).
    if last_node == snapshot:
        parent = None
        try:
            parent = snapshot.parents.all()[0]
        except IndexError:
            pass
        if parent:
            # Call this function again on this parent.
            return unmatch_snapshot_tree(parent.pk)

    parents = last_node.parent_tree
    can = last_node.canonical_building

    if last_node != snapshot:
        # If we're not dealing with a leaf node, we need to remerge.
        remaining_tree = set(parents) - set(children) - set([snapshot])
        # We do this because sets don't preserve order, and we need it.
        remaining_ancestors = filter(lambda x: x in remaining_tree, parents)

        # Take whatever parts of the tree that were unaffected and re-merge
        # them.
        if remaining_ancestors:
            new_root = remaining_ancestors[0]
            for parent in remaining_ancestors[1:]:
                new_root = save_snapshot_match(new_root.pk, parent.pk)

        # Remove the stale Snapshots.
        for child in children:
            child.delete()

    if can:
        # How would this ever not have a canonical building, though?
        can.canonical_snapshot = new_root
        can.save()
        new_root.canonical_building = can
        new_root.save()

    # Regardless of our snapshot's origins we create a new tree for it.
    snap_can = snapshot.canonical_building
    if snap_can and snap_can != can and not snap_can.active:
        snap_can.active = True
        snap_can.canonical_snapshot = snap_can.canonical_snapshot or snapshot
        snap_can.save()

    else:
        snapshot.canonical_building = CanonicalBuilding.objects.create(
            canonical_snapshot=snapshot
        )
        snapshot.save()


def _get_filtered_values(updated_values):
    """Breaks out mappable, meta and source BuildingSnapshot attributes."""
    from seed.utils.constants import META_FIELDS, EXCLUDE_FIELDS
    mappable_values = {}
    meta_values = {}
    source_values = {}

    for item in updated_values:
        value = updated_values[item]
        if item.endswith('_source'):
            source_values[item] = value
        elif item in META_FIELDS:
            meta_values[item] = value
        elif item not in EXCLUDE_FIELDS:
            mappable_values[item] = value

    return mappable_values, meta_values, source_values


def _get_diff_sources(mappable, old_snapshot):
    """Return a list of str for values that changed from old_snapshot."""
    results = []
    for item in mappable:
        value = mappable[item]
        if getattr(old_snapshot, item, None) != value and value:
            results.append(item)

    return results


def update_building(old_snapshot, updated_values, user, *args, **kwargs):
    """Creates a new snapshot with updated values."""
    from seed.mappings import seed_mappings, mapper as seed_mapper

    mappable, meta, sources = _get_filtered_values(updated_values)

    canon = old_snapshot.canonical_building or None
    # Need to hydrate sources
    sources = {
        k: BuildingSnapshot.objects.get(pk=v) for k, v in sources.items() if v
    }

    # Handle the mapping of "normal" attributes.
    new_snapshot = mapper.map_row(
        mappable,
        dict(seed_mappings.BuildingSnapshot_to_BuildingSnapshot),
        BuildingSnapshot,
        initial_data=sources  # Copy parent's source attributes.
    )

    diff_sources = _get_diff_sources(mappable, old_snapshot)
    for diff in diff_sources:
        setattr(new_snapshot, '{0}_source'.format(diff), new_snapshot)

    # convert dates to something django likes
    new_snapshot.clean()
    new_snapshot.canonical_building = canon
    new_snapshot.save()
    # All all the orgs the old snapshot had.
    new_snapshot.super_organization = old_snapshot.super_organization
    # Move the meta data over.
    for meta_val in meta:
        setattr(new_snapshot, meta_val, meta[meta_val])
    # Insert new_snapshot into the inheritence chain
    old_snapshot.children.add(new_snapshot)
    new_snapshot.import_file = old_snapshot.import_file

    # Update/override anything in extra data.
    extra, sources = seed_mapper.merge_extra_data(
        new_snapshot, old_snapshot, default=new_snapshot
    )
    new_snapshot.extra_data = extra
    new_snapshot.extra_data_sources = sources
    new_snapshot.save()

    # If we had a canonical building and its can_snapshot was old, update.
    if canon and canon.canonical_snapshot == old_snapshot:
        canon.canonical_snapshot = new_snapshot
        canon.save()

    return new_snapshot


def get_column_mapping(column_raw, organization, source_type=ASSESSED_RAW):
    """Callable provided to MCM to return a previously mapped field."""
    try:
        previous_mapping = ColumnMapping.objects.get(
            super_organization=organization,
            column_raw=column_raw,
            source_type=source_type
        )

        return (previous_mapping.column_mapped, 1.0)

    except ColumnMapping.DoesNotExist:
        return None


def get_column_mappings(organization, source_type=ASSESSED_RAW):
    """Returns dict of all the column mappings for an Org's given source type

    :param organization: inst, Organization.
    :param source_type: int, one of the ``SEED_DATA_SOURCES``.

    :returns list of dict:

    Use this when actually performing mapping between datasources, but
    only call it after all of the mappings have been saved to the
    ``ColumnMapping`` table.

    """
    source_mappings = ColumnMapping.objects.filter(
        super_organization=organization, source_type=source_type
    )

    return {
        item.column_raw: item.column_mapped
        for item in source_mappings if item.column_mapped
    }


class Project(TimeStampedModel):
    INACTIVE_STATUS = 0
    ACTIVE_STATUS = 1
    STATUS_CHOICES = (
        (INACTIVE_STATUS, _('Inactive')),
        (ACTIVE_STATUS, _('Active')),
    )

    name = models.CharField(_('name'), max_length=PROJECT_NAME_MAX_LENGTH)
    slug = AutoSlugField(
        _('slug'), populate_from='name', unique=True, editable=True
    )
    owner = models.ForeignKey(
        User, verbose_name=_('User'), blank=True, null=True
    )
    last_modified_by = models.ForeignKey(
        User, blank=True, null=True, related_name='last_modified_user'
    )
    super_organization = models.ForeignKey(
        SuperOrganization,
        verbose_name=_('SeedOrg'),
        blank=True,
        null=True,
        related_name='projects'
    )
    description = models.TextField(_('description'), blank=True, null=True)
    status = models.IntegerField(
        _('status'), choices=STATUS_CHOICES, default=ACTIVE_STATUS
    )
    building_snapshots = models.ManyToManyField(
        'BuildingSnapshot', through="ProjectBuilding", blank=True, null=True
    )

    @property
    def adding_buildings_status_percentage_cache_key(self):
        return "SEED_PROJECT_ADDING_BUILDINGS_PERCENTAGE_%s" % self.slug

    @property
    def removing_buildings_status_percentage_cache_key(self):
        return "SEED_PROJECT_REMOVING_BUILDINGS_PERCENTAGE_%s" % self.slug

    @property
    def has_compliance(self):
        return self.compliance_set.exists()

    def __unicode__(self):
        return u"Project %s" % (self.name, )

    def get_compliance(self):
        if self.has_compliance:
            return self.compliance_set.all()[0]
        else:
            return None

    def to_dict(self):
        return obj_to_dict(self)


class ProjectBuilding(TimeStampedModel):
    building_snapshot = models.ForeignKey(
        'BuildingSnapshot', related_name='project_building_snapshots'
    )
    project = models.ForeignKey(
        'Project', related_name='project_building_snapshots'
    )
    compliant = models.NullBooleanField(null=True, )
    approved_date = models.DateField(_("approved_date"), null=True, blank=True)
    approver = models.ForeignKey(
        User, verbose_name=_('User'), blank=True, null=True
    )
    status_label = models.ForeignKey('StatusLabel', null=True, blank=True)

    class Meta:
        ordering = ['project', 'building_snapshot']
        unique_together = ('building_snapshot', 'project')
        verbose_name = _("project building")
        verbose_name_plural = _("project buildings")

    def __unicode__(self):
        return u"{0} - {1}".format(self.building_snapshot, self.project.name)

    def to_dict(self):
        return obj_to_dict(self)


class StatusLabel(TimeStampedModel):
    RED_CHOICE = 'red'
    ORANGE_CHOICE = 'orange'
    WHITE_CHOICE = 'white'
    BLUE_CHOICE = 'blue'
    LIGHT_BLUE_CHOICE = 'light blue'
    GREEN_CHOICE = 'green'

    COLOR_CHOICES = (
        (RED_CHOICE, _('red')),
        (BLUE_CHOICE, _('blue')),
        (LIGHT_BLUE_CHOICE, _('light blue')),
        (GREEN_CHOICE, _('green')),
        (WHITE_CHOICE, _('white')),
        (ORANGE_CHOICE, _('orange')),
    )

    name = models.CharField(_('name'), max_length=PROJECT_NAME_MAX_LENGTH)
    color = models.CharField(
        _('compliance_type'),
        max_length=30,
        choices=COLOR_CHOICES,
        default=GREEN_CHOICE
    )
    super_organization = models.ForeignKey(
        SuperOrganization,
        verbose_name=_('SeedOrg'),
        blank=True,
        null=True,
        related_name='status_labels'
    )

    class Meta:
        unique_together = ('name', 'super_organization')
        ordering = ['-name']

    def __unicode__(self):
        return u"{0} - {1}".format(self.name, self.color)

    def to_dict(self):
        return obj_to_dict(self)


class Compliance(TimeStampedModel):
    BENCHMARK_COMPLIANCE_CHOICE = 'Benchmarking'
    AUDITING_COMPLIANCE_CHOICE = 'Auditing'
    RETRO_COMMISSIONING_COMPLIANCE_CHOICE = 'Retro Commissioning'
    COMPLIANCE_CHOICES = (
        (BENCHMARK_COMPLIANCE_CHOICE, _('Benchmarking')),
        (AUDITING_COMPLIANCE_CHOICE, _('Auditing')),
        (RETRO_COMMISSIONING_COMPLIANCE_CHOICE, _('Retro Commissioning')),
    )

    compliance_type = models.CharField(
        _('compliance_type'),
        max_length=30,
        choices=COMPLIANCE_CHOICES,
        default=BENCHMARK_COMPLIANCE_CHOICE
    )
    start_date = models.DateField(_("start_date"), null=True, blank=True)
    end_date = models.DateField(_("end_date"), null=True, blank=True)
    deadline_date = models.DateField(_("deadline_date"), null=True, blank=True)
    project = models.ForeignKey(Project, verbose_name=_('Project'),)

    def __unicode__(self):
        return u"Compliance %s for project %s" % (
            self.compliance_type, self.project
        )

    def to_dict(self):
        return obj_to_dict(self)


class CustomBuildingHeaders(models.Model):
    """Specify custom building header mapping for display."""
    super_organization = models.ForeignKey(
        SuperOrganization,
        blank=True,
        null=True,
        verbose_name=_('SeedOrg'),
        related_name='custom_headers'
    )

    # 'existing, normalized name' -> 'preferred display name'
    # e.g. {'district': 'Boro'}
    building_headers = JSONField()

    objects = ExpressionManager()


class ColumnMapping(models.Model):
    """Stores previous user-defined column mapping.

    We'll pull from this when pulling from varried, dynamic
    source data to present the user with previous choices for that
    same field in subsequent data loads.

    """
    class Meta:
        unique_together = ('super_organization', 'column_raw', 'source_type')

    user = models.ForeignKey(User, blank=True, null=True)
    super_organization = models.ForeignKey(
        SuperOrganization,
        verbose_name=_('SeedOrg'),
        blank=True,
        null=True,
        related_name='column_mappings'
    )
    # Like in BuildingSnapshot, this tells us where our column_raw comes from.
    source_type = models.IntegerField(choices=SEED_DATA_SOURCES)
    column_raw = models.CharField(max_length=512)  # Value we're mapping from
    # Value we're mapping to
    column_mapped = models.CharField(max_length=128, blank=True, null=True)


class CanonicalManager(models.Manager):
    """Manager to add useful model filtering methods"""
    def get_queryset(self):
        """Return only active CanonicalBuilding rows."""
        return super(CanonicalManager, self).get_queryset().filter(
            active=True
        )


class CanonicalBuilding(models.Model):
    """
    One Table to rule them all, One Table to find them, One Table to bring
    them all and in the database bind them.
    """

    canonical_snapshot = models.ForeignKey(
        "BuildingSnapshot", blank=True, null=True, on_delete=models.SET_NULL
    )
    active = models.BooleanField(default=True)

    objects = models.Manager()
    manager = CanonicalManager()

    def __unicode__(self):
        snapshot_pk = "None"
        if self.canonical_snapshot:
            snapshot_pk = self.canonical_snapshot.pk

        return u"pk: {0} - snapshot: {1} - active: {2}".format(
            self.pk,
            snapshot_pk,
            self.active
        )


class BuildingSnapshot(TimeStampedModel):
    """The periodical composite of a building from disparate data sources.

    Represents the best data between all the datasources for a given building,
    potentially merged together with other BuildingSnapshot instances'
    attribute values.

    Two BuildingSnapshots can create a child, forming a match between
    buildings. Thusly, a BuildingSnapshot's co-parent is the other parent of
    its child. The m2m field `children` with related name `parents` allow the
    traversal of the tree. A BuildingSnapshot can have one parent in
    the case where an edit to data was initiated by a user, and the original
    field is preserved (treating BuildingSnapshots as immutable objects) and
    a new BuildingSnapshot is created with the change.

    """

    super_organization = models.ForeignKey(
        SuperOrganization,
        blank=True,
        null=True,
        related_name='building_snapshots'
    )
    import_file = models.ForeignKey(ImportFile, null=True, blank=True)
    canonical_building = models.ForeignKey(
        CanonicalBuilding, blank=True, null=True, on_delete=models.SET_NULL
    )

    # Denormalized Data and sources.
    # e.g. which model does this denormalized data come frome?

    tax_lot_id = models.CharField(max_length=128, null=True, blank=True)
    tax_lot_id_source = models.ForeignKey(
        'BuildingSnapshot', related_name='+', null=True, blank=True
    )

    pm_property_id = models.CharField(max_length=128, null=True, blank=True)
    pm_property_id_source = models.ForeignKey(
        'BuildingSnapshot', related_name='+', null=True, blank=True
    )

    custom_id_1 = models.CharField(max_length=128, null=True, blank=True)
    custom_id_1_source = models.ForeignKey(
        'BuildingSnapshot', related_name='+', null=True, blank=True
    )

    lot_number = models.CharField(max_length=128, null=True, blank=True)
    lot_number_source = models.ForeignKey(
        'BuildingSnapshot', related_name='+', null=True, blank=True
    )

    block_number = models.CharField(max_length=128, null=True, blank=True)
    block_number_source = models.ForeignKey(
        'BuildingSnapshot', related_name='+', null=True, blank=True
    )

    # Tax IDs are often stuck in here.
    property_notes = models.TextField(null=True, blank=True)
    property_notes_source = models.ForeignKey(
        'BuildingSnapshot', related_name='+', null=True, blank=True
    )

    year_ending = models.DateField(null=True, blank=True)
    year_ending_source = models.ForeignKey(
        'BuildingSnapshot', related_name='+', null=True, blank=True
    )

    # e.g. 'Ward', 'Borough', 'Boro', etc.
    district = models.CharField(max_length=128, null=True, blank=True)
    district_source = models.ForeignKey(
        'BuildingSnapshot', related_name='+', null=True, blank=True
    )

    owner = models.CharField(max_length=128, null=True, blank=True)
    owner_source = models.ForeignKey(
        'BuildingSnapshot', related_name='+', null=True, blank=True
    )

    owner_email = models.CharField(max_length=128, null=True, blank=True)
    owner_email_source = models.ForeignKey(
        'BuildingSnapshot', related_name='+', null=True, blank=True
    )

    owner_telephone = models.CharField(max_length=128, null=True, blank=True)
    owner_telephone_source = models.ForeignKey(
        'BuildingSnapshot', related_name='+', null=True, blank=True
    )

    owner_address = models.CharField(max_length=128, null=True, blank=True)
    owner_address_source = models.ForeignKey(
        'BuildingSnapshot', related_name='+', null=True, blank=True
    )

    owner_city_state = models.CharField(max_length=128, null=True, blank=True)
    owner_city_state_source = models.ForeignKey(
        'BuildingSnapshot', related_name='+', null=True, blank=True
    )

    owner_postal_code = models.CharField(max_length=128, null=True, blank=True)
    owner_postal_code_source = models.ForeignKey(
        'BuildingSnapshot', related_name='+', null=True, blank=True
    )

    property_name = models.CharField(max_length=255, null=True, blank=True)
    property_name_source = models.ForeignKey(
        'BuildingSnapshot', related_name='+', null=True, blank=True
    )

    building_count = models.IntegerField(max_length=3, null=True, blank=True)
    building_count_source = models.ForeignKey(
        'BuildingSnapshot', related_name='+', null=True, blank=True
    )

    gross_floor_area = models.FloatField(null=True, blank=True)
    gross_floor_area_source = models.ForeignKey(
        'BuildingSnapshot', related_name='+', null=True, blank=True
    )

    address_line_1 = models.CharField(max_length=255, null=True, blank=True)
    address_line_1_source = models.ForeignKey(
        'BuildingSnapshot', related_name='+', null=True, blank=True
    )

    address_line_2 = models.CharField(max_length=255, null=True, blank=True)
    address_line_2_source = models.ForeignKey(
        'BuildingSnapshot', related_name='+', null=True, blank=True
    )

    city = models.CharField(max_length=255, null=True, blank=True)
    city_source = models.ForeignKey(
        'BuildingSnapshot', related_name='+', null=True, blank=True
    )

    postal_code = models.CharField(max_length=255, null=True, blank=True)
    postal_code_source = models.ForeignKey(
        'BuildingSnapshot', related_name='+', null=True, blank=True
    )

    year_built = models.IntegerField(null=True, blank=True)
    year_built_source = models.ForeignKey(
        'BuildingSnapshot', related_name='+', null=True, blank=True
    )

    recent_sale_date = models.DateTimeField(null=True, blank=True)
    recent_sale_date_source = models.ForeignKey(
        'BuildingSnapshot', related_name='+', null=True, blank=True
    )

    energy_score = models.IntegerField(null=True, blank=True)
    energy_score_source = models.ForeignKey(
        'BuildingSnapshot', related_name='+', null=True, blank=True
    )

    site_eui = models.FloatField(null=True, blank=True)
    site_eui_source = models.ForeignKey(
        'BuildingSnapshot', related_name='+', null=True, blank=True
    )

    generation_date = models.DateTimeField(null=True, blank=True)
    generation_date_source = models.ForeignKey(
        'BuildingSnapshot', related_name='+', null=True, blank=True
    )

    release_date = models.DateTimeField(null=True, blank=True)
    release_date_source = models.ForeignKey(
        'BuildingSnapshot', related_name='+', null=True, blank=True
    )

    state_province = models.CharField(max_length=255, null=True, blank=True)
    state_province_source = models.ForeignKey(
        'BuildingSnapshot', related_name='+', null=True, blank=True
    )

    site_eui_weather_normalized = models.FloatField(null=True, blank=True)
    site_eui_weather_normalized_source = models.ForeignKey(
        'BuildingSnapshot', related_name='+', null=True, blank=True
    )

    source_eui = models.FloatField(null=True, blank=True)
    source_eui_source = models.ForeignKey(
        'BuildingSnapshot', related_name='+', null=True, blank=True
    )

    source_eui_weather_normalized = models.FloatField(null=True, blank=True)
    source_eui_weather_normalized_source = models.ForeignKey(
        'BuildingSnapshot', related_name='+', null=True, blank=True
    )

    energy_alerts = models.TextField(null=True, blank=True)
    energy_alerts_source = models.ForeignKey(
        'BuildingSnapshot', related_name='+', null=True, blank=True
    )

    space_alerts = models.TextField(null=True, blank=True)
    space_alerts_source = models.ForeignKey(
        'BuildingSnapshot', related_name='+', null=True, blank=True
    )

    building_certification = models.CharField(
        max_length=255, null=True, blank=True
    )
    building_certification_source = models.ForeignKey(
        'BuildingSnapshot', related_name='+', null=True, blank=True
    )

    conditioned_floor_area = models.FloatField(null=True, blank=True)
    conditioned_floor_area_source = models.ForeignKey(
        'BuildingSnapshot', related_name='+', null=True, blank=True
    )

    occupied_floor_area = models.FloatField(null=True, blank=True)
    occupied_floor_area_source = models.ForeignKey(
        'BuildingSnapshot', related_name='+', null=True, blank=True
    )

    use_description = models.TextField(null=True, blank=True)
    use_description_source = models.ForeignKey(
        'BuildingSnapshot', related_name='+', null=True, blank=True
    )

    #
    ## Meta Data
    ###

    children = models.ManyToManyField(
        'BuildingSnapshot',
        null=True,
        blank=True,
        symmetrical=False,
        related_name='parents',
    )

    best_guess_confidence = models.FloatField(null=True, blank=True)
    best_guess_canonical_building = models.ForeignKey(
        'CanonicalBuilding', related_name='best_guess', blank=True, null=True
    )

    # This is set for composite BS instances.
    # 1 if system matched, 2 if manually matched.
    match_type = models.IntegerField(
        choices=SEED_MATCH_TYPES, null=True, blank=True
    )
    # How we determine which subset of `'BuildingSnapshot'` to bubble up.
    confidence = models.FloatField(null=True, blank=True)
    # Setting NULL/BLANK so we can use get_or_create.
    last_modified_by = models.ForeignKey(User, null=True, blank=True)
    # Tells us whether this is pulled from AS-Raw data, PM-Raw data, or BS.
    source_type = models.IntegerField(
        choices=SEED_DATA_SOURCES, null=True, blank=True
    )

    # None if Snapshot is not canonical, otherwise points to Dataset pk.
    canonical_for_ds = models.ForeignKey(
        ImportRecord, null=True, blank=True, related_name='+'
    )

    #
    ## JSON data
    ###

    # 'key' -> 'value'
    extra_data = JSONField()
    # 'key' -> ['model', 'fk'], what was the model and its FK?
    extra_data_sources = JSONField()

    objects = ExpressionManager()

    def clean(self, *args, **kwargs):
        super(BuildingSnapshot, self).clean(*args, **kwargs)
        date_field_names = (
            'year_ending',
            'generation_date',
            'release_date',
            'recent_sale_date'
        )
        if self.custom_id_1 and len(self.custom_id_1) > 128:
            self.custom_id_1 = self.custom_id_1[:128]
        for field in date_field_names:
            value = getattr(self, field)
            if value and isinstance(value, basestring):
                setattr(self, field, convert_datestr(value))

    def to_dict(self, fields=None):
        """
        Returns a dict version of this building, either with all fields
        or masked to just those requested.
        """
        if fields:
            return {
                field: getattr(self, field) for field in fields
            }
        return obj_to_dict(self)

    def __unicode__(self):
        u_repr = u'id: {0}, pm_property_id: {1}, tax_lot_id: {2},' + \
            ' confidence: {3}'
        return u_repr.format(
            self.pk, self.pm_property_id, self.tax_lot_id, self.confidence
        )

    @property
    def co_parent(self):
        """returns the first co-parent as a BuildingSnapshot inst"""
        if not self.children.all().exists():
            return
        first_child = self.children.all()[0]
        for parent in first_child.parents.all():
            if parent.pk != self.pk:
                return parent

    @property
    def co_parents(self):
        """returns co-parents for a BuildingSnapshot as a queryset"""
        return BuildingSnapshot.objects.filter(
            children__parents=self
        ).exclude(pk=self.pk)

    def recurse_tree(self, attr):
        """Recurse M2M relationship tree, extending list as we go.

        :param attr: str, name of attribute we wish to traverse.
            .e.g. 'children', or 'parents'

        """
        nodes = []
        node_type = getattr(self, attr)
        # N.B. We're expecting a Django M2M attribute here.
        for node in node_type.all():
            nodes.extend(node.recurse_tree(attr))

        nodes.extend(node_type.all())

        return nodes

    @property
    def child_tree(self):
        """Recurse to give us a merge-order list of children."""
        # Because we traverse down, we need to revese to get merge-order
        children = self.recurse_tree('children')
        children.reverse()
        return children

    @property
    def parent_tree(self):
        """Recurse to give us merge-order list of parents."""
        # No need to reverse, we create merge-order by going backwards
        return self.recurse_tree('parents')


class AttributeOption(models.Model):
    """Holds a single conflicting value for a BuildingSnapshot attribute."""
    value = models.CharField(max_length=255)
    value_source = models.IntegerField(choices=SEED_DATA_SOURCES)
    building_variant = models.ForeignKey(
        'BuildingAttributeVariant',
        null=True,
        blank=True,
        related_name='options'
    )


class BuildingAttributeVariant(models.Model):
    """Place to keep the options of BuildingSnapshot attribute variants.

    When we want to select which source's values should sit in the Canonical
    Building's position, we need to draw from a set of options determined
    during the matching phase. We should only have one 'Variant' container
    per field_name, per snapshot.

    """
    class Meta:
        unique_together = ('field_name', 'building_snapshot')

    field_name = models.CharField(max_length=255)
    building_snapshot = models.ForeignKey(
        BuildingSnapshot, related_name='variants', null=True, blank=True
    )


class Meter(models.Model):
    """Meter specific attributes."""
    name = models.CharField(max_length=100)
    building_snapshot = models.ManyToManyField(
        BuildingSnapshot, related_name='meters', null=True, blank=True
    )
    energy_type = models.IntegerField(max_length=3, choices=ENERGY_TYPES)
    energy_units = models.IntegerField(max_length=3, choices=ENERGY_UNITS)


class TimeSeries(models.Model):
    """For storing engergy use over time."""
    begin_time = models.DateTimeField(null=True, blank=True)
    end_time = models.DateTimeField(null=True, blank=True)
    reading = models.FloatField(null=True)
    cost = models.DecimalField(max_digits=11, decimal_places=4, null=True)
    meter = models.ForeignKey(
        Meter, related_name='timeseries_data', null=True, blank=True
    )
