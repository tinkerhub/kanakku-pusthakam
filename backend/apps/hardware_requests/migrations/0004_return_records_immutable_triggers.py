from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ("hardware_requests", "0003_requesteraccountability_returnevent"),
    ]

    operations = [
        migrations.RunSQL(
            sql="""
CREATE OR REPLACE FUNCTION hardware_requests_return_records_reject_mutation()
RETURNS trigger
LANGUAGE plpgsql
AS $$
BEGIN
    RAISE EXCEPTION 'append-only/immutable table: % not allowed', TG_OP;
END;
$$;

CREATE TRIGGER hardware_requests_returnevent_no_update
BEFORE UPDATE ON hardware_requests_returnevent
FOR EACH ROW EXECUTE FUNCTION hardware_requests_return_records_reject_mutation();

CREATE TRIGGER hardware_requests_returnevent_no_delete
BEFORE DELETE ON hardware_requests_returnevent
FOR EACH ROW EXECUTE FUNCTION hardware_requests_return_records_reject_mutation();

CREATE TRIGGER hardware_requests_requesteraccountability_no_update
BEFORE UPDATE ON hardware_requests_requesteraccountability
FOR EACH ROW EXECUTE FUNCTION hardware_requests_return_records_reject_mutation();

CREATE TRIGGER hardware_requests_requesteraccountability_no_delete
BEFORE DELETE ON hardware_requests_requesteraccountability
FOR EACH ROW EXECUTE FUNCTION hardware_requests_return_records_reject_mutation();
""",
            reverse_sql="""
DROP TRIGGER IF EXISTS hardware_requests_returnevent_no_update ON hardware_requests_returnevent;
DROP TRIGGER IF EXISTS hardware_requests_returnevent_no_delete ON hardware_requests_returnevent;
DROP TRIGGER IF EXISTS hardware_requests_requesteraccountability_no_update ON hardware_requests_requesteraccountability;
DROP TRIGGER IF EXISTS hardware_requests_requesteraccountability_no_delete ON hardware_requests_requesteraccountability;
DROP FUNCTION IF EXISTS hardware_requests_return_records_reject_mutation();
""",
        ),
    ]
