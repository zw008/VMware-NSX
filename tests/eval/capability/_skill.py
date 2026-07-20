"""The only repo-specific facts in this capability suite.

Every ``test_*.py`` file in this directory is identical across the family repos;
they differ only through this module. Keeping the difference in one small file is
what makes a rubric change portable — edit the eval once, copy it, and the scores
stay comparable between skills.
"""

from __future__ import annotations

#: Import path of the Python package under test.
PACKAGE = "vmware_nsx"

#: Module holding the FastMCP server.
SERVER_MODULE = "vmware_nsx.mcp_server.server"

#: CLI entry point name, used when scoring whether an error names something
#: concrete for the operator to run.
CLI_NAME = "vmware-nsx"

#: Companion skills this one legitimately routes to. A required entity name that
#: this surface cannot produce is not a dead end *if* the description says which
#: sibling skill produces it — that is a documented hand-off rather than a gap.
COMPANION_SKILLS = (
    "vmware-aiops",
    "vmware-monitor",
    "vmware-storage",
    "vmware-vks",
    "vmware-nsx",
    "vmware-nsx-security",
    "vmware-aria",
    "vmware-avi",
    "vmware-harden",
    "vmware-pilot",
)

#: Entity tokens this skill's tools name, mapped to the words its listing tools
#: use. Authored from the registry's own required parameters, not from the
#: domain in the abstract. Drives ``test_entity_reachability``: a stem that is
#: not here is invisible to that eval, which is why the suite asserts coverage.
#: ``transport_zone_path`` ends in ``_path`` rather than an id suffix but is
#: still a lookup against ``list_transport_zones``, so it is matched whole.
ENTITY_WORDS = {
    'segment': ('segment', 'segments'),
    'tier0': ('tier0', 'tier0_gateway', 'tier0_gateways'),
    'tier1': ('tier1', 'tier1_gateway', 'tier1_gateways'),
    'nat_rule': ('rule', 'rules', 'nat_rule', 'nat_rules'),
    'route': ('route', 'routes', 'static_route', 'static_routes'),
    'ip_pool': ('pool', 'pools', 'ip_pool', 'ip_pools'),
    'edge_cluster': ('cluster', 'clusters', 'edge_cluster', 'edge_clusters'),
    'transport_node': ('node', 'nodes', 'transport_node', 'transport_nodes'),
    'transport_zone': ('zone', 'zones', 'transport_zone', 'transport_zones', 'transport_zone_path'),
    'vm': ('vm', 'vms', 'vm_display'),
}

#: Skill-specific parameters that end in an entity suffix but are supplied by the
#: operator rather than discovered from an API. Universal exclusions (``target``,
#: paths, filters) live in the eval itself.
NOT_AN_ENTITY = frozenset(
    {
        # The name of the segment/gateway/pool being created — the operator
        # chooses it. The creation-verb rule does not catch it because the
        # stem is "display", not the entity.
        'display_name',
    }
)

def get_server(module):
    """Return the FastMCP instance ``SERVER_MODULE`` exposes.

    The family has two shapes: a module-level ``mcp`` built at import time, and a
    ``build_server()`` factory (vmware-harden, vmware-debug). Declared per skill
    rather than probed with a try/except chain — a fallback would let a server
    that stops exposing what this file says silently resolve to the other shape,
    and the suite would go on scoring something nobody meant to measure.
    """
    return module.mcp
