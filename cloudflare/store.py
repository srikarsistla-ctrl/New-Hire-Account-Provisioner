"""One bounded D1 document for the shared hackathon sandbox, with atomic CAS."""
import json
from fastapi import HTTPException
from cloudflare.state import initial_state

MAX_STATE_BYTES = 900_000


class Store:
    def __init__(self, binding):
        self.db = binding

    async def load(self):
        row = await self.db.prepare('SELECT version, payload FROM sandbox_state WHERE id = 1').first()
        if row is None:
            raise HTTPException(503, 'Database is not initialized. Apply the Cloudflare D1 migration.')
        # JS proxies in Workers; dicts in local tests.
        version = row['version'] if isinstance(row, dict) else row.version
        payload = row['payload'] if isinstance(row, dict) else row.payload
        return version, json.loads(payload) if payload else initial_state()

    async def save(self, version, state):
        payload = json.dumps(state, separators=(',', ':'), ensure_ascii=True)
        if len(payload.encode()) > MAX_STATE_BYTES:
            raise HTTPException(507, 'The shared demo has reached its storage limit. Export the records and ask the owner to archive the demo database.')
        result = await self.db.prepare('UPDATE sandbox_state SET payload = ?, version = version + 1 WHERE id = 1 AND version = ?').bind(payload, version).run()
        changes = result['meta']['changes'] if isinstance(result, dict) else result.meta.changes
        if changes != 1:
            raise HTTPException(409, 'Another request changed the demo while this operation was running. Reload and retry; this operation was not saved.')
