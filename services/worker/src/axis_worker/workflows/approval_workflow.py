from temporalio import workflow


@workflow.defn
class ApprovalWorkflow:
    def __init__(self) -> None:
        self._approved: bool | None = None

    @workflow.run
    async def run(self, payload: dict) -> dict:
        await workflow.wait_condition(lambda: self._approved is not None)
        return {
            "status": "approved" if self._approved else "rejected",
            "payload": payload,
        }

    @workflow.signal
    async def approve(self, approved: bool) -> None:
        self._approved = approved
