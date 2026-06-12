from django.db import migrations


class Migration(migrations.Migration):
    dependencies = [
        ("boxes", "0005_qrcode_qrscanevent_qrcode_uniq_active_qr_per_target"),
    ]

    operations = [
        migrations.RunSQL(
            sql="""
CREATE OR REPLACE FUNCTION boxes_qrscanevent_reject_mutation()
RETURNS trigger
LANGUAGE plpgsql
AS $$
BEGIN
    RAISE EXCEPTION 'append-only/immutable table: % not allowed', TG_OP;
END;
$$;

CREATE TRIGGER boxes_qrscanevent_no_update
BEFORE UPDATE ON boxes_qrscanevent
FOR EACH ROW EXECUTE FUNCTION boxes_qrscanevent_reject_mutation();

CREATE TRIGGER boxes_qrscanevent_no_delete
BEFORE DELETE ON boxes_qrscanevent
FOR EACH ROW EXECUTE FUNCTION boxes_qrscanevent_reject_mutation();
""",
            reverse_sql="""
DROP TRIGGER IF EXISTS boxes_qrscanevent_no_update ON boxes_qrscanevent;
DROP TRIGGER IF EXISTS boxes_qrscanevent_no_delete ON boxes_qrscanevent;
DROP FUNCTION IF EXISTS boxes_qrscanevent_reject_mutation();
""",
        )
    ]

