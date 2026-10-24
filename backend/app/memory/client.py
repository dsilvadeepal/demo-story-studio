"""Lazy managed Mem0 adapter. No OSS/vector-store initialization or implicit extraction."""
import os
from pathlib import Path
from typing import Protocol


class MemoryClient(Protocol):
    def add(self,text,scope,correlation): ...
    def search(self,query,scope): ...
    def update(self,id,text,scope,correlation): ...
    def get(self,id): ...
    def delete(self,id): ...


class ManagedMemoryClient:
    def __init__(self): self._client=None
    @property
    def client(self):
        if self._client is None:
            os.environ['MEM0_TELEMETRY']='false'
            # The SDK creates a local config directory even for managed API use.
            # Keep that state inside the ignored project folder, not the user's home.
            local_dir=Path(__file__).resolve().parents[3]/'.local'/'mem0'
            local_dir.mkdir(parents=True,exist_ok=True,mode=0o700)
            os.environ['MEM0_DIR']=str(local_dir)
            from mem0 import MemoryClient as SDKClient
            self._client=SDKClient(api_key=os.environ['MEM0_API_KEY'])
        return self._client
    def add(self,text,scope,correlation):
        response=self.client.add(text,user_id=scope['owner'],metadata=dict(scope,correlation=correlation),infer=False)
        results=response.get('results',[])
        if len(results)==1 and results[0].get('id'):return self.get(results[0]['id'])
        return None  # Accepted/queued is not a verified save.
    def search(self,query,scope):
        filters={'AND':[{'user_id':scope['owner']},*({'metadata':{k:v}} for k,v in scope.items())]}
        return self.client.search(query,filters=filters,top_k=5).get('results',[])
    def update(self,id,text,scope,correlation):
        self.client.update(id,text=text,metadata=dict(scope,correlation=correlation))
        return self.get(id)
    def get(self,id):
        try:return self.client.get(id)
        except Exception as error:
            # Only the SDK's explicit not-found response confirms remote absence.
            from mem0.exceptions import MemoryNotFoundError
            if isinstance(error,MemoryNotFoundError):return None
            raise
    def delete(self,id):return self.client.delete(id)
