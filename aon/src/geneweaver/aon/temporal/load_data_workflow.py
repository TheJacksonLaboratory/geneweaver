from datetime import timedelta
from typing import Optional

from temporalio import workflow
from temporalio.common import RetryPolicy

with workflow.unsafe.imports_passed_through():
    from geneweaver.aon.temporal.activities.download_source import (
        create_schema_activity,
        get_data_activity,
        load_agr_activity,
        load_gw_activity,
        load_homology_activity,
        mark_load_complete_activity,
        release_exists_activity,
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
                retry_policy=RetryPolicy(
                    maximum_attempts=1,
                ),
            )

            gw_load_success = await workflow.execute_activity(
                load_gw_activity,
                schema_id,
                schedule_to_close_timeout=timedelta(seconds=36000),
                retry_policy=RetryPolicy(
                    maximum_attempts=1,
                ),
            )

            homology_load_success = await workflow.execute_activity(
                load_homology_activity,
                schema_id,
                schedule_to_close_timeout=timedelta(seconds=360),
                retry_policy=RetryPolicy(
                    maximum_attempts=3,
                ),
            )

            if agr_load_success and gw_load_success and homology_load_success:
                await workflow.execute_activity(
                    mark_load_complete_activity,
                    schema_id,
                    schedule_to_close_timeout=timedelta(seconds=60),
                )

            return agr_load_success and gw_load_success and homology_load_success
