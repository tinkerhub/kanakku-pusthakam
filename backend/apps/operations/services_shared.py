from apps.boxes.models import Box


def _container(container_id, makerspace_id):
    if not container_id:
        return None
    return Box.objects.get(pk=container_id, makerspace_id=makerspace_id)
