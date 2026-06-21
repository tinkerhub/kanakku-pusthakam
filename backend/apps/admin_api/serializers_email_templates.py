from rest_framework import serializers

from apps.integrations.email_render import sanitize_email_html


class EmailVariableSerializer(serializers.Serializer):
    name = serializers.CharField()
    description = serializers.CharField()
    sample = serializers.CharField()
    trusted_html = serializers.BooleanField()


class EmailTemplateRowSerializer(serializers.Serializer):
    key = serializers.CharField()
    family = serializers.CharField()
    audience = serializers.CharField()
    label = serializers.CharField()
    variables = EmailVariableSerializer(many=True)
    subject = serializers.CharField()
    text_body = serializers.CharField()
    html_body = serializers.CharField(allow_blank=True)
    is_active = serializers.BooleanField()
    is_customized = serializers.BooleanField()


class EmailTemplateWriteSerializer(serializers.Serializer):
    subject = serializers.CharField(max_length=255)
    text_body = serializers.CharField(allow_blank=False)
    html_body = serializers.CharField(allow_blank=True, required=False, default="")
    is_active = serializers.BooleanField(default=True)


class EmailLayoutSerializer(serializers.Serializer):
    html = serializers.CharField(allow_blank=True)
    is_active = serializers.BooleanField(default=True)
    is_default = serializers.BooleanField(read_only=True)

    def validate_html(self, value):
        # A non-blank layout MUST keep the content slot — otherwise render_email_template's
        # `.replace("{{ content }}", body)` drops the message body from every HTML email
        # for this makerspace. (Blank html is allowed: the renderer then uses the default.)
        # Check the SANITIZED value, since nh3 may strip markup the token lived in (e.g. a
        # disallowed attribute) — so the API returns a clean 400 rather than a model 500.
        if value.strip() and "{{ content }}" not in sanitize_email_html(value):
            raise serializers.ValidationError(
                "The layout must contain the {{ content }} token."
            )
        return value


class EmailRenderedSerializer(serializers.Serializer):
    subject = serializers.CharField()
    text_body = serializers.CharField()
    html_body = serializers.CharField(allow_blank=True)


class EmailPreviewRequestSerializer(serializers.Serializer):
    # Optional draft fields — when present, the preview renders the UNSAVED editor content
    # instead of the stored/default template.
    subject = serializers.CharField(required=False, allow_blank=True)
    text_body = serializers.CharField(required=False, allow_blank=True)
    html_body = serializers.CharField(required=False, allow_blank=True)
