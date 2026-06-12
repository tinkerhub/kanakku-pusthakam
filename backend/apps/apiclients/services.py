def sync_makerspace_origins(makerspace):
    # Global clients (makerspace=None) have no makerspace CORS list to sync; the
    # admin update/delete paths pass None for them, so no-op instead of crashing.
    if makerspace is None:
        return
    origins = set()
    for client in makerspace.api_clients.filter(is_active=True):
        origins.update(client.allowed_origins or [])
    makerspace.cors_allowed_origins = sorted(origins)
    makerspace.save(update_fields=["cors_allowed_origins", "updated_at"])
