import asyncio

from temporalio.client import Client
from temporalio.worker import Worker

from geneweaver.aon.temporal.activities.download_source import (
    get_data_activity,
    release_exists_activity,
    create_schema_activity,
    load_agr_activity,
    load_gw_activity,
    load_homology_activity,
    mark_load_complete_activity,
)
from geneweaver.aon.temporal.load_data_workflow import GeneWeaverAonDataLoad

from geneweaver.aon.core.config import config


async def main():
    client = await Client.connect(config.TEMPORAL_URI,
                                  namespace=config.TEMPORAL_NAMESPACE)

    worker = Worker(
        client,
        task_queue=config.TEMPORAL_TASK_QUEUE,
        workflows=[GeneWeaverAonDataLoad],
        activities=[
            get_data_activity,
            release_exists_activity,
            create_schema_activity,
            load_agr_activity,
            load_gw_activity,
            load_homology_activity,
            mark_load_complete_activity,
        ],
    )

    await worker.run()


if __name__ == "__main__":
    asyncio.run(main())
