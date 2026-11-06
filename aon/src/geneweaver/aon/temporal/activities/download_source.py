"""TemporalIO activities for downloading AGR data."""

from typing import Optional, Tuple

from geneweaver.aon.cli.load import (
    agr_release_exists,
    create_schema,
    get_data,
    gw,
    homology,
    load_agr,
    mark_schema_version_load_complete,
)
from temporalio import activity


@activity.defn
async def get_data_activity(release: Optional[str] = None) -> Tuple[str, str]:
    """Get AGR data for a release."""
    return get_data(release)


@activity.defn
async def release_exists_activity(release: str) -> bool:
    """Check if an AGR release exists."""
    return agr_release_exists(release)


@activity.defn
async def create_schema_activity(release: str) -> Tuple[str, int]:
    """Create a new schema version."""
    return create_schema(release)


@activity.defn
async def load_agr_activity(orthology_file: str, schema_id: int) -> bool:
    """Load AGR data for a schema version."""
    return load_agr(orthology_file, schema_id)


@activity.defn
async def load_gw_activity(schema_id: int) -> bool:
    """Load GeneWeaver data for a schema version."""
    return gw(schema_id)


@activity.defn
async def load_homology_activity(schema_id: int) -> bool:
    """Load homology data for a schema version."""
    return homology(schema_id)


@activity.defn
async def mark_load_complete_activity(schema_id: int) -> bool:
    """Mark the load of a schema version as complete."""
    return mark_schema_version_load_complete(schema_id)
