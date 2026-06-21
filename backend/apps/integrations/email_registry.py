from apps.integrations.email_registry_hardware import HARDWARE_TEMPLATES
from apps.integrations.email_registry_printing import PRINTING_TEMPLATES


EMAIL_TEMPLATES = {**HARDWARE_TEMPLATES, **PRINTING_TEMPLATES}


def get_template(key):
    return EMAIL_TEMPLATES[key]


def template_keys():
    return list(EMAIL_TEMPLATES)


def templates_for_actions(actions: set[str]):
    return {
        key: template
        for key, template in EMAIL_TEMPLATES.items()
        if template["action"] in actions
    }
