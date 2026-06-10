from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ("boxes", "0003_boxscan"),
    ]

    operations = [
        migrations.RunSQL(
            sql="""
CREATE OR REPLACE FUNCTION boxscan_reject_mutation()
RETURNS trigger
LANGUAGE plpgsql
AS $$
BEGIN
    RAISE EXCEPTION 'append-only/immutable table: % not allowed', TG_OP;
END;
$$;

CREATE TRIGGER boxes_boxscan_no_update
BEFORE UPDATE ON boxes_boxscan
FOR EACH ROW EXECUTE FUNCTION boxscan_reject_mutation();

CREATE TRIGGER boxes_boxscan_no_delete
BEFORE DELETE ON boxes_boxscan
FOR EACH ROW EXECUTE FUNCTION boxscan_reject_mutation();
""",
            reverse_sql="""
DROP TRIGGER IF EXISTS boxes_boxscan_no_update ON boxes_boxscan;
DROP TRIGGER IF EXISTS boxes_boxscan_no_delete ON boxes_boxscan;
DROP FUNCTION IF EXISTS boxscan_reject_mutation();
""",
        ),
    ]
