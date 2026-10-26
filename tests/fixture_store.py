"""Local JSON fixture, not production locking/durability infrastructure."""
import copy
from contextlib import contextmanager
import json
from pathlib import Path
class Store:
    def __init__(self,directory): self.path=Path(directory)/'fixture.json'
    @contextmanager
    def locked(self):
        self.records=json.loads(self.path.read_text()) if self.path.exists() else {}
        yield self
    def get(self,key): return copy.deepcopy(self.records.get(key))
    def save(self,key,value): self.save_many({key:value})
    def save_many(self,updates):
        self.records.update(copy.deepcopy(updates)); self.path.write_text(json.dumps(self.records))
