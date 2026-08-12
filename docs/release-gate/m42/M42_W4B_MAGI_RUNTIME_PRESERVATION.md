# M42 Wave 4B — Runtime Preservation

Production edits enqueue only via `api.imageProduct.editEnqueue` → ImageEditIntent path.

No Magi package builders. Deferred/Blocked actions call `/api/magi/deferred/{id}/execute` and never execute.
