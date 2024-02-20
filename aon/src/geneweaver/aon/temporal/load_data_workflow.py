from datetime import timedelta
from typing import Optional, Tuple

from temporalio import workflow

with workflow.unsafe.imports_passed_through():
    from geneweaver.aon.temporal.activities.download_source import (
        get_data_activity,
        release_exists_activity,
        create_schema_activity,
        load_agr_activity,
        load_gw_activity,
        load_homology_activity,
        mark_load_complete_activity,
    )


@workflow.defn
class GeneWeaverAonDataLoad:
    @workflow.run
    async def run(self, release: Optional[str] = None) -> bool:
        orthology_file, release = await workflow.execute_activity(
            get_data_activity,
            release,
            schedule_to_close_timeout=timedelta(seconds=15),
        )

        release_exists = await workflow.execute_activity(
            release_exists_activity,
            release,
            schedule_to_close_timeout=timedelta(seconds=15),
        )
        if release_exists is True:
            return False

        elif release_exists is False:

            schema_name, schema_id = await workflow.execute_activity(
                create_schema_activity,
                release,
                schedule_to_close_timeout=timedelta(seconds=15),
            )

            agr_load_success = await workflow.execute_activity(
                load_agr_activity,
                args=(orthology_file, schema_id),
                schedule_to_close_timeout=timedelta(seconds=3600),
            )

            gw_load_success = await workflow.execute_activity(
                load_gw_activity,
                schema_id,
                schedule_to_close_timeout=timedelta(seconds=36000),
            )

            homology_load_success = await workflow.execute_activity(
                load_homology_activity,
                args=schema_id,
                schedule_to_close_timeout=timedelta(seconds=6000),
            )

            if agr_load_success and gw_load_success and homology_load_success:
                await workflow.execute_activity(
                    mark_load_complete_activity,
                    schema_id,
                    schedule_to_close_timeout=timedelta(seconds=15),
                )

            return agr_load_success and gw_load_success and homology_load_success
